"""
RUDRA AI - FastAPI Main Entry Point
The central backend server that hosts all API routes and manages application lifecycle.
"""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database.sqlite_db import init_database, set_db_path
from app.routers import chat, system, automation
from app.services.wake_word_service import wake_word_service

# ─── Logging Setup ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rudra_ai")


# ─── Application Lifecycle ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info("  RUDRA AI Backend Starting...")
    logger.info("  Version: %s", settings.APP_VERSION)
    logger.info("  Debug: %s", settings.DEBUG)
    logger.info("=" * 60)

    # Initialize database
    set_db_path(settings.DB_PATH)
    await init_database()
    logger.info("Database initialized at %s", settings.DB_PATH)

    # Create necessary directories
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Start the always-on wake word listener for "Rudra"
    wake_word_service.start_listening()
    logger.info("Wake-word listener active. Say 'Rudra' to wake the assistant.")

    logger.info("RUDRA AI Backend ready on http://%s:%d", settings.HOST, settings.PORT)

    yield

    # Shutdown
    logger.info("RUDRA AI Backend shutting down...")


# ─── FastAPI App ─────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered desktop assistant backend",
    lifespan=lifespan,
)

# ─── CORS Middleware ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "app://-",                 # Electron production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Include Routers ─────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(system.router)
app.include_router(automation.router)


# ─── Root Endpoint ───────────────────────────────────────────────────
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    from app.services.llm_service import llm_service
    ollama_status = await llm_service.check_ollama_status()

    return {
        "backend": "healthy",
        "ollama": ollama_status,
        "database": "connected",
    }


# ─── Run Server ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
