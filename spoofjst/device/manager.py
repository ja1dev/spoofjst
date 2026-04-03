"""Device detection and connection lifecycle management."""

from __future__ import annotations

import asyncio
import gc
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pymobiledevice3.lockdown import LockdownClient, create_using_usbmux
from pymobiledevice3.usbmux import list_devices

from spoofjst.config import DEVICE_POLL_INTERVAL
from spoofjst.device.tunnel import TunnelManager
from spoofjst.device.location import LocationService

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    udid: str
    name: str
    model: str
    ios_version: str
    developer_mode: bool
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "udid": self.udid,
            "name": self.name,
            "model": self.model,
            "ios_version": self.ios_version,
            "developer_mode": self.developer_mode,
            "connected": self.connected,
        }


class DeviceManager:
    """Manages iOS device detection, tunnel, and location spoofing."""

    def __init__(self) -> None:
        self.device_info: DeviceInfo | None = None
        self.lockdown: LockdownClient | None = None
        self.tunnel: TunnelManager = TunnelManager()
        self.location: LocationService = LocationService()
        self._poll_task: asyncio.Task | None = None
        self._listeners: list[Callable] = []
        self._connect_lock: asyncio.Lock = asyncio.Lock()

    def add_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify(self, event: str, data: dict[str, Any] | None = None) -> None:
        for cb in list(self._listeners):  # iterate copy to avoid mutation issues
            try:
                await cb(event, data or {})
            except Exception:
                logger.exception("Listener error")

    async def start_polling(self) -> None:
        """Start background USB device polling."""
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_loop())
            logger.info("Device polling started")

    async def stop_polling(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._check_devices()
            except Exception:
                logger.exception("Poll error")
            await asyncio.sleep(DEVICE_POLL_INTERVAL)

    async def _check_devices(self) -> None:
        """Check for USB-connected iOS devices."""
        try:
            devices = await list_devices()
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            # usbmuxd not running — no devices possible
            if self.device_info is not None:
                await self.disconnect()
                await self._notify("device_disconnected")
            return

        if not devices and self.device_info is not None:
            logger.info("Device disconnected: %s", self.device_info.name)
            await self.disconnect()
            await self._notify("device_disconnected")
            return

        if devices and self.device_info is None:
            if self._connect_lock.locked():
                return
            async with self._connect_lock:
                if self.device_info is not None:
                    return
                dev = devices[0]
                udid = dev.serial
                logger.info("Device detected: %s", udid)
                await self._connect(udid)

    async def _connect(self, udid: str) -> None:
        """Connect to a device by UDID: lockdown, read info, start tunnel."""
        try:
            self.lockdown = await create_using_usbmux(serial=udid)

            all_values = await self.lockdown.get_value()
            name = all_values.get("DeviceName", "Unknown")
            model = all_values.get("ProductType", "Unknown")
            ios_version = all_values.get("ProductVersion", "0.0")

            # Check developer mode (iOS 16+)
            dev_mode = True
            try:
                val = await self.lockdown.get_value(domain="com.apple.security.mac.amfi", key="DeveloperModeStatus")
                if val is not None:
                    dev_mode = bool(val)
            except Exception:
                pass

            self.device_info = DeviceInfo(
                udid=udid,
                name=name,
                model=model,
                ios_version=ios_version,
                developer_mode=dev_mode,
            )

            await self._notify("device_connected", self.device_info.to_dict())

            gc.collect()

            if not self.device_info.developer_mode:
                await self._notify("developer_mode_needed", self.device_info.to_dict())
                return

            # Start tunnel for iOS 17+
            major = int(ios_version.split(".")[0])
            if major >= 17:
                await self._notify("tunnel_status", {"status": "connecting"})
                success = await self.tunnel.start(udid)
                if success:
                    await self._notify("tunnel_status", {"status": "connected"})
                    self.location.set_service_provider(await self.tunnel.get_service_provider())
                else:
                    await self._notify("tunnel_status", {"status": "error", "message": "Failed to establish tunnel"})
            else:
                self.location.set_service_provider(self.lockdown)
                await self._notify("tunnel_status", {"status": "connected"})

        except Exception as e:
            logger.exception("Failed to connect to device %s", udid)
            await self._notify("tunnel_status", {"status": "error", "message": str(e)})
            self.device_info = None
            self.lockdown = None

    async def disconnect(self) -> None:
        """Disconnect from current device and tear down tunnel."""
        await self.location.clear_provider()
        await self.tunnel.stop()
        self.lockdown = None
        self.device_info = None

    async def reveal_developer_mode(self) -> dict[str, Any]:
        """Reveal the Developer Mode toggle in Settings (no Xcode needed)."""
        if self.lockdown is None:
            return {"success": False, "error": "No device connected"}
        try:
            from pymobiledevice3.services.amfi import AmfiService
            amfi = AmfiService(self.lockdown)
            await amfi.reveal_developer_mode_option_in_ui()
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to reveal Developer Mode")
            return {"success": False, "error": str(e)}

    async def recheck_developer_mode(self) -> dict[str, Any]:
        """Re-check Developer Mode status and continue connection if enabled."""
        if self.device_info is None or self.lockdown is None:
            return {"success": False, "error": "No device connected"}
        try:
            val = await self.lockdown.get_value(
                domain="com.apple.security.mac.amfi", key="DeveloperModeStatus"
            )
            dev_mode = bool(val) if val is not None else False
            self.device_info.developer_mode = dev_mode

            if dev_mode:
                # Developer Mode now enabled — continue with tunnel setup
                ios_version = self.device_info.ios_version
                major = int(ios_version.split(".")[0])
                if major >= 17:
                    await self._notify("tunnel_status", {"status": "connecting"})
                    success = await self.tunnel.start(self.device_info.udid)
                    if success:
                        await self._notify("tunnel_status", {"status": "connected"})
                        self.location.set_service_provider(await self.tunnel.get_service_provider())
                    else:
                        await self._notify("tunnel_status", {"status": "error", "message": "Failed to establish tunnel"})
                else:
                    self.location.set_service_provider(self.lockdown)
                    await self._notify("tunnel_status", {"status": "connected"})
                return {"success": True, "developer_mode": True}
            else:
                return {"success": True, "developer_mode": False}
        except Exception as e:
            logger.exception("Failed to recheck Developer Mode")
            return {"success": False, "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Return current device + tunnel + location status."""
        if self.device_info is None:
            return {"device": None, "tunnel": "disconnected", "spoofed_location": None}

        return {
            "device": self.device_info.to_dict(),
            "tunnel": self.tunnel.status,
            "spoofed_location": self.location.current_location,
        }
