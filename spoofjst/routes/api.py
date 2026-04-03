"""REST API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from spoofjst.models.schemas import LocationRequest, LocationResponse, ClearResponse

router = APIRouter(prefix="/api")


@router.get("/device")
async def get_device(request: Request):
    """Return current device and connection status."""
    manager = request.app.state.device_manager
    return manager.get_status()


@router.post("/location/set", response_model=LocationResponse)
async def set_location(request: Request, body: LocationRequest):
    """Set spoofed GPS location."""
    manager = request.app.state.device_manager
    result = await manager.location.set_location(body.lat, body.lon)

    if result["success"]:
        # Notify WebSocket listeners
        await manager._notify("location_set", {"lat": body.lat, "lon": body.lon})

    return result


@router.post("/location/clear", response_model=ClearResponse)
async def clear_location(request: Request):
    """Restore real GPS location."""
    manager = request.app.state.device_manager
    result = await manager.location.clear_location()

    if result["success"]:
        await manager._notify("location_cleared", {})

    return result


@router.post("/developer-mode/reveal")
async def reveal_developer_mode(request: Request):
    """Reveal Developer Mode toggle in iPhone Settings."""
    manager = request.app.state.device_manager
    return await manager.reveal_developer_mode()


@router.post("/developer-mode/recheck")
async def recheck_developer_mode(request: Request):
    """Re-check if Developer Mode has been enabled."""
    manager = request.app.state.device_manager
    return await manager.recheck_developer_mode()
