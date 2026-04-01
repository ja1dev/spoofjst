"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from spoofjst.device.manager import DeviceManager
from spoofjst.routes.api import router as api_router
from spoofjst.routes.ws import router as ws_router, device_event_handler

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start device polling on startup, stop on shutdown."""
    manager: DeviceManager = app.state.device_manager
    manager.add_listener(device_event_handler)
    await manager.start_polling()
    yield
    await manager.stop_polling()
    await manager.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(title="spoofjst", version="0.1.0", lifespan=lifespan)
    app.state.device_manager = DeviceManager()

    app.include_router(api_router)
    app.include_router(ws_router)

    # Serve frontend static files (HTML, CSS, JS)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
