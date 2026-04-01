"""Location simulation via pymobiledevice3 DVT services."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Re-send spoofed location every N seconds to keep it active for Find My
LOCATION_REFRESH_INTERVAL = 2.0


class LocationService:
    """Wraps pymobiledevice3's LocationSimulation for set/clear operations.

    Keeps the DVT connection open and periodically re-sends the spoofed
    location so that iOS services like Find My iPhone see the fake position.
    """

    def __init__(self) -> None:
        self._service_provider = None
        self.current_location: dict[str, float] | None = None
        self._dvt = None
        self._loc_sim = None
        self._refresh_task: asyncio.Task | None = None

    def set_service_provider(self, provider) -> None:
        """Set the service provider (LockdownClient or RemoteServiceDiscoveryService)."""
        self._service_provider = provider

    async def clear_provider(self) -> None:
        await self._close_session()
        self._service_provider = None
        self.current_location = None

    async def _ensure_session(self) -> None:
        """Open DVT + LocationSimulation if not already open."""
        if self._loc_sim is not None:
            return

        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

        self._dvt = DvtProvider(lockdown=self._service_provider)
        await self._dvt.__aenter__()

        self._loc_sim = LocationSimulation(self._dvt)
        await self._loc_sim.__aenter__()

        logger.info("DVT location session opened")

    async def _close_session(self) -> None:
        """Close DVT + LocationSimulation if open."""
        self._stop_refresh()

        if self._loc_sim is not None:
            try:
                await self._loc_sim.__aexit__(None, None, None)
            except Exception:
                pass
            self._loc_sim = None

        if self._dvt is not None:
            try:
                await self._dvt.__aexit__(None, None, None)
            except Exception:
                pass
            self._dvt = None

        logger.info("DVT location session closed")

    def _stop_refresh(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

    async def _refresh_loop(self) -> None:
        """Periodically re-send the current spoofed location."""
        try:
            while True:
                await asyncio.sleep(LOCATION_REFRESH_INTERVAL)
                if self.current_location and self._loc_sim:
                    try:
                        await self._loc_sim.set(
                            self.current_location["lat"],
                            self.current_location["lon"],
                        )
                    except Exception:
                        logger.exception("Location refresh failed, reopening session")
                        await self._close_session()
                        break
        except asyncio.CancelledError:
            pass

    async def set_location(self, lat: float, lon: float) -> dict[str, Any]:
        """Spoof the device location to the given coordinates."""
        if self._service_provider is None:
            return {"success": False, "error": "No device connected"}

        try:
            await self._ensure_session()
            await self._loc_sim.set(lat, lon)
            self.current_location = {"lat": lat, "lon": lon}

            # Start or restart the refresh loop
            self._stop_refresh()
            self._refresh_task = asyncio.create_task(self._refresh_loop())

            logger.info("Location set to %f, %f", lat, lon)
            return {"success": True, "lat": lat, "lon": lon}
        except Exception as e:
            logger.exception("Failed to set location")
            await self._close_session()
            return {"success": False, "error": str(e)}

    async def clear_location(self) -> dict[str, Any]:
        """Restore real GPS location."""
        if self._service_provider is None:
            return {"success": False, "error": "No device connected"}

        try:
            if self._loc_sim is not None:
                await self._loc_sim.clear()
            await self._close_session()
            self.current_location = None
            logger.info("Location cleared")
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to clear location")
            await self._close_session()
            return {"success": False, "error": str(e)}
