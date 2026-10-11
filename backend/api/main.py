"""
backend/api/main.py
FastAPI application entrypoint for Flowstate.

Routers mounted:
  - /upload   — manual file upload (existing, unchanged)
  - /webhook  — real-time OpenClaw event receiver (Phase 2)

Lifespan tasks started on startup:
  - GmailConnector polling loop (runs every GMAIL_POLL_INTERVAL_SEC seconds)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from backend.ingestion.upload import router as upload_router
from backend.api.routes.webhook import router as webhook_router
from backend.infrastructure.connectors.gmail_connector import GmailConnector

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Config                                                                #
# ------------------------------------------------------------------ #

# The team whose Gmail inbox to watch on startup.
# In a multi-tenant setup, start one task per team or drive from DB.
STARTUP_TEAM_ID: str = os.getenv("STARTUP_TEAM_ID", "default_team")


# ------------------------------------------------------------------ #
# Lifespan — startup / shutdown                                         #
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    On startup:
      - Creates a GmailConnector for STARTUP_TEAM_ID.
      - Starts the polling loop as an asyncio background task.

    On shutdown:
      - Cancels the polling task gracefully.
    """
    logger.info("[lifespan] Flowstate API starting up…")

    connector = GmailConnector(team_id=STARTUP_TEAM_ID)
    polling_task = asyncio.create_task(
        connector.run_polling_loop(team_id=STARTUP_TEAM_ID),
        name=f"gmail_polling_{STARTUP_TEAM_ID}",
    )
    logger.info(
        "[lifespan] Gmail polling task started for team %s (task: %s)",
        STARTUP_TEAM_ID, polling_task.get_name(),
    )

    yield  # application is running

    # ---- Shutdown ----
    logger.info("[lifespan] Flowstate API shutting down — cancelling Gmail polling task…")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("[lifespan] Gmail polling task cancelled cleanly.")
    finally:
        connector.close()


# ------------------------------------------------------------------ #
# App                                                                   #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Flowstate API",
    description=(
        "AI-powered workflow orchestration. Extracts structured tasks from "
        "unstructured communications via file upload or real-time connectors."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ---- Routers ----
app.include_router(upload_router)                        # POST /upload
app.include_router(webhook_router)                       # POST /webhook


# ------------------------------------------------------------------ #
# Health check                                                          #
# ------------------------------------------------------------------ #

@app.get("/", tags=["health"], summary="Health check")
def root() -> dict:
    return {"status": "Flowstate is running", "version": "2.0.0"}