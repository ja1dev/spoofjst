"""Device detection and connection lifecycle management."""

from __future__ import annotations

import asyncio
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

    def add_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify(self, event: str, data: dict[str, Any] | None = None) -> None:
        for cb in self._listeners:
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
        devices = await asyncio.to_thread(list_devices)

        if not devices and self.device_info is not None:
            # Device was disconnected
            logger.info("Device disconnected: %s", self.device_info.name)
            await self.disconnect()
            await self._notify("device_disconnected")
            return

        if devices and self.device_info is None:
            # New device detected — connect to first one
            dev = devices[0]
            udid = dev.serial
            logger.info("Device detected: %s", udid)
            await self._connect(udid)

    async def _connect(self, udid: str) -> None:
        """Connect to a device by UDID: lockdown, read info, start tunnel."""
        try:
            self.lockdown = await asyncio.to_thread(create_using_usbmux, serial=udid)

            all_values = await asyncio.to_thread(lambda: dict(self.lockdown.all_values))
            name = all_values.get("DeviceName", "Unknown")
            model = all_values.get("ProductType", "Unknown")
            ios_version = all_values.get("ProductVersion", "0.0")

            # Check developer mode (iOS 16+)
            dev_mode = True
            try:
                dev_mode = await asyncio.to_thread(
                    lambda: self.lockdown.get_value(domain="com.apple.security.mac.amfi", key="DeveloperModeStatus")
                )
                if dev_mode is None:
                    dev_mode = True  # Pre-iOS 16 doesn't have this
            except Exception:
                pass

            self.device_info = DeviceInfo(
                udid=udid,
                name=name,
                model=model,
                ios_version=ios_version,
                developer_mode=bool(dev_mode),
            )

            await self._notify("device_connected", self.device_info.to_dict())

            if not self.device_info.developer_mode:
                await self._notify("tunnel_status", {"status": "error", "message": "Developer Mode is not enabled. Enable it in Settings > Privacy & Security > Developer Mode."})
                return

            # Start tunnel for iOS 17+
            major = int(ios_version.split(".")[0])
            if major >= 17:
                await self._notify("tunnel_status", {"status": "connecting"})
                success = await self.tunnel.start(udid)
                if success:
                    await self._notify("tunnel_status", {"status": "connected"})
                    self.location.set_service_provider(self.tunnel.get_service_provider())
                else:
                    await self._notify("tunnel_status", {"status": "error", "message": "Failed to establish tunnel"})
            else:
                # iOS < 17: use lockdown directly
                self.location.set_service_provider(self.lockdown)
                await self._notify("tunnel_status", {"status": "connected"})

        except Exception as e:
            logger.exception("Failed to connect to device %s", udid)
            await self._notify("tunnel_status", {"status": "error", "message": str(e)})
            self.device_info = None
            self.lockdown = None

    async def disconnect(self) -> None:
        """Disconnect from current device and tear down tunnel."""
        self.location.clear_provider()
        await self.tunnel.stop()
        self.lockdown = None
        self.device_info = None

    def get_status(self) -> dict[str, Any]:
        """Return current device + tunnel + location status."""
        if self.device_info is None:
            return {"device": None, "tunnel": "disconnected", "spoofed_location": None}

        return {
            "device": self.device_info.to_dict(),
            "tunnel": self.tunnel.status,
            "spoofed_location": self.location.current_location,
        }
