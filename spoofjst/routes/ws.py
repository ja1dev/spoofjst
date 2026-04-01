"""WebSocket endpoint for real-time device status updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict) -> None:
        message = json.dumps({"event": event, "data": data})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


ws_manager = ConnectionManager()


async def device_event_handler(event: str, data: dict) -> None:
    """Bridge between DeviceManager events and WebSocket broadcasts."""
    await ws_manager.broadcast(event, data)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)

    # Send current status immediately on connect
    device_manager = websocket.app.state.device_manager
    status = device_manager.get_status()
    await websocket.send_text(json.dumps({"event": "status", "data": status}))

    try:
        while True:
            # Keep connection alive; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
