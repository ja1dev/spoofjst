"""Location simulation via pymobiledevice3 DVT services."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LocationService:
    """Wraps pymobiledevice3's LocationSimulation for set/clear operations."""

    def __init__(self) -> None:
        self._service_provider = None
        self.current_location: dict[str, float] | None = None

    def set_service_provider(self, provider) -> None:
        """Set the service provider (LockdownClient or RemoteServiceDiscoveryService)."""
        self._service_provider = provider

    def clear_provider(self) -> None:
        self._service_provider = None
        self.current_location = None

    async def set_location(self, lat: float, lon: float) -> dict[str, Any]:
        """Spoof the device location to the given coordinates."""
        if self._service_provider is None:
            return {"success": False, "error": "No device connected"}

        try:
            await asyncio.to_thread(self._set_location_sync, lat, lon)
            self.current_location = {"lat": lat, "lon": lon}
            logger.info("Location set to %f, %f", lat, lon)
            return {"success": True, "lat": lat, "lon": lon}
        except Exception as e:
            logger.exception("Failed to set location")
            return {"success": False, "error": str(e)}

    def _set_location_sync(self, lat: float, lon: float) -> None:
        """Synchronous location set — runs in thread."""
        from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

        with DvtSecureSocketProxyService(lockdown=self._service_provider) as dvt:
            LocationSimulation(dvt).set(lat, lon)

    async def clear_location(self) -> dict[str, Any]:
        """Restore real GPS location."""
        if self._service_provider is None:
            return {"success": False, "error": "No device connected"}

        try:
            await asyncio.to_thread(self._clear_location_sync)
            self.current_location = None
            logger.info("Location cleared")
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to clear location")
            return {"success": False, "error": str(e)}

    def _clear_location_sync(self) -> None:
        """Synchronous location clear — runs in thread."""
        from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

        with DvtSecureSocketProxyService(lockdown=self._service_provider) as dvt:
            LocationSimulation(dvt).clear()
