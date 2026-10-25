"""
Saber Trader — AI Stock Signal Bot for IDX
Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""

    # --- STARTUP ---
    logger.info("🚀 Saber Trader AI Signal Bot starting up...")
    logger.info(f"   Environment: {settings.APP_ENV}")
    logger.info(f"   Data Provider: {settings.DATA_PROVIDER}")
    logger.info(f"   LLM Provider: {settings.LLM_PROVIDER}")

    # Initialize database
    try:
        from database.db import init_db
        await init_db()
        logger.info("   ✅ Database initialized")
    except Exception as e:
        logger.warning(f"   ⚠️ Database init skipped: {e}")

    # Start scheduler
    scheduler = None
    if settings.APP_ENV != "testing":
        try:
            from jobs.scheduler import create_scheduler
            scheduler = create_scheduler()
            scheduler.start()
            logger.info("   ✅ Scheduler started")
        except Exception as e:
            logger.warning(f"   ⚠️ Scheduler start failed: {e}")

    logger.info("🟢 Saber Trader ready!")

    yield

    # --- SHUTDOWN ---
    logger.info("🔴 Saber Trader shutting down...")

    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("   Scheduler stopped")

    try:
        from database.db import close_db
        await close_db()
        logger.info("   Database closed")
    except Exception:
        pass

    logger.info("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title="Saber Trader — AI Stock Signal Bot",
    description=(
        "AI-powered stock signal bot for the Indonesian Stock Exchange (IDX). "
        "Uses deterministic scoring engine for BUY/SELL decisions. "
        "LLM is only used for analyst opinion writing."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - clean Telegram Bot & Scheduler service
@app.get("/")
async def root():
    """Root endpoint — Telegram Bot & Scheduler status."""
    return {
        "status": "online",
        "service": "Saber Trader Telegram Screener Bot",
        "timestamp": datetime.now().isoformat(),
        "env": settings.APP_ENV,
        "day_trade_mode": settings.DAY_TRADE_MODE,
        "chart_interval": settings.CHART_INTERVAL,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }

