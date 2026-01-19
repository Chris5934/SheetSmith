"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from ..agent import SheetSmithAgent
from ..config import settings
from .routes import router

# Global agent instance
_agent: Optional[SheetSmithAgent] = None


def get_agent() -> SheetSmithAgent:
    """Get the global agent instance."""
    global _agent
    if _agent is None:
        _agent = SheetSmithAgent()
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    agent = get_agent()
    await agent.initialize()
    yield
    # Shutdown
    await agent.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SheetSmith",
        description="Agentic Google Sheets Automation Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(router, prefix="/api")

    # Serve static files (frontend)
    static_dir = Path(__file__).parent.parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def serve_frontend():
            """Serve the frontend."""
            return FileResponse(str(static_dir / "index.html"))

    return app
