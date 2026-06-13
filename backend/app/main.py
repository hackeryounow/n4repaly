"""
N4Relay — PFCP UDP Relay with Web UI
Main entry point: initializes relay, interceptor, template store, and FastAPI app.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import load_config
from .relay.server import RelayServer
from .relay.interceptor import Interceptor
from .relay.templates import TemplateStore
from .api.routes import router, set_dependencies
from .api.websocket import ConnectionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global components (initialized in lifespan)
# ---------------------------------------------------------------------------
config = load_config()
relay = RelayServer(config)
interceptor = Interceptor(max_held=config.intercept.max_held)
template_store = TemplateStore()
ws_manager = ConnectionManager()

# Wire components together
interceptor.set_relay(relay)
relay.interceptor = interceptor
relay.template_store = template_store
set_dependencies(relay, interceptor, template_store)


# ---------------------------------------------------------------------------
# Wire WebSocket callbacks on the relay
# ---------------------------------------------------------------------------
async def _on_new_packet(packet: dict):
    await ws_manager.broadcast_packet(packet)


async def _on_new_intercept(packet: dict):
    await ws_manager.broadcast_intercept(packet)


relay.on_packet(_on_new_packet)
relay.on_intercept(_on_new_intercept)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle"""
    logger.info("N4Relay starting up …")

    # Load persisted templates
    await template_store.load_from_disk()

    # Auto-start relay
    try:
        await relay.start()
        logger.info("Relay auto-started")
    except Exception:
        logger.exception("Failed to auto-start relay")

    yield  # ---- app runs ----

    logger.info("N4Relay shutting down …")
    await relay.stop()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="N4Relay", version="1.0.0", lifespan=lifespan)

# REST routes
app.include_router(router)


# WebSocket endpoints
@app.websocket("/ws/packets")
async def ws_packets(ws: WebSocket):
    await ws_manager.connect_packet(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive; clients rarely send
    except WebSocketDisconnect:
        await ws_manager.disconnect_packet(ws)


@app.websocket("/ws/intercepted")
async def ws_intercepts(ws: WebSocket):
    await ws_manager.connect_intercept(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect_intercept(ws)


# ---------------------------------------------------------------------------
# Serve frontend static files (built with Vite)
# ---------------------------------------------------------------------------
_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _frontend_dist.exists():
    # Serve static assets (js/css/images)
    app.mount(
        "/assets",
        StaticFiles(directory=str(_frontend_dist / "assets")),
        name="static-assets",
    )

    # Serve index.html for all non-API routes (SPA)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Try exact file first
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Fall back to index.html for SPA routing
        return FileResponse(str(_frontend_dist / "index.html"))
else:
    logger.warning(f"Frontend dist not found at {_frontend_dist}, UI will not be available")


# ---------------------------------------------------------------------------
# Entry point (python -m backend.app.main)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = config.web.host
    port = config.web.port
    logger.info(f"Starting N4Relay web server on {host}:{port}")
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )
