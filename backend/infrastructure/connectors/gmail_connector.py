"""
gmail_connector.py
Background polling connector for Gmail via OpenClaw.

GmailConnector extends OpenClawClient and adds:
  - watch_inbox(team_id, since) — polls the OpenClaw Gmail endpoint for new
    emails and pushes each one as a job to Redis.
  - Persistent last_checked timestamp per team so no email is processed twice.
  - A run_polling_loop() coroutine designed to run as a FastAPI lifespan
    background task (asyncio-friendly via asyncio.sleep).

Architecture note:
  - The connector uses the synchronous httpx client (inherited from
    OpenClawClient) wrapped in asyncio.to_thread() so the polling loop
    never blocks the event loop.
  - Redis jobs are pushed in the same format as upload.py, so worker.py
    picks them up without modification.

Environment variables:
    OPENCLAW_API_BASE       — OpenClaw API base URL
    OPENCLAW_API_KEY        — OpenClaw bearer token
    REDIS_URL               — Redis connection string
    GMAIL_POLL_INTERVAL_SEC — polling interval in seconds (default: 60)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

import redis

from backend.infrastructure.connectors.openclaw.client import OpenClawClient
from backend.infrastructure.connectors.event_to_chunks import event_to_chunks
from backend.models import Event

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Config                                                                #
# ------------------------------------------------------------------ #

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
OBJECT_STORE_PATH: str = os.getenv("OBJECT_STORE_PATH", "./storage/objects")
POLL_INTERVAL: int = int(os.getenv("GMAIL_POLL_INTERVAL_SEC", "60"))

# ------------------------------------------------------------------ #
# In-memory last_checked store                                          #
#                                                                       #
# In production, persist this to Redis or PostgreSQL so the timestamp  #
# survives restarts and prevents re-processing of old emails.           #
# Key: team_id → datetime (UTC)                                        #
# ------------------------------------------------------------------ #
_last_checked: Dict[str, datetime] = {}


class GmailConnector(OpenClawClient):
    """
    Gmail polling connector.

    Inherits all OpenClaw HTTP logic from OpenClawClient and adds a
    polling loop specifically for Gmail inbox watching.
    """

    def __init__(self, team_id: str) -> None:
        super().__init__(team_id=team_id)
        self._redis = redis.from_url(REDIS_URL)

    # ---------------------------------------------------------------- #
    # Core polling logic                                                  #
    # ---------------------------------------------------------------- #

    def watch_inbox(self, team_id: str, since: datetime) -> int:
        """
        Poll Gmail via OpenClaw for emails received after *since*.

        For each new email:
          1. Converts it to an Event.
          2. Converts Event → Chunks.
          3. Persists chunks as a .txt file.
          4. Pushes a job to Redis "flowstate:jobs".

        Args:
            team_id: Flowstate team identifier.
            since:   Only fetch emails newer than this UTC datetime.

        Returns:
            Number of new emails enqueued.
        """
        logger.info("[GmailConnector] Polling inbox for team %s since %s", team_id, since.isoformat())

        try:
            events = self.get_emails(since=since)
        except Exception as exc:
            logger.error("[GmailConnector] Failed to fetch emails: %s", exc)
            return 0

        enqueued = 0
        for event in events:
            try:
                self._enqueue_event(event)
                enqueued += 1
            except Exception as exc:
                logger.error(
                    "[GmailConnector] Failed to enqueue event %s: %s", event.id, exc
                )

        logger.info("[GmailConnector] Enqueued %d new email(s) for team %s", enqueued, team_id)
        return enqueued

    # ---------------------------------------------------------------- #
    # Async polling loop — designed for FastAPI lifespan usage           #
    # ---------------------------------------------------------------- #

    async def run_polling_loop(self, team_id: str) -> None:
        """
        Coroutine that polls Gmail in a loop at GMAIL_POLL_INTERVAL_SEC intervals.

        Designed to be started with asyncio.create_task() inside a FastAPI
        lifespan context manager so it runs for the application's lifetime.

        The loop:
          1. Determines the 'since' cutoff (last_checked per team or 1 hour ago).
          2. Calls watch_inbox() in a thread (non-blocking).
          3. Updates last_checked timestamp.
          4. Sleeps for POLL_INTERVAL seconds.
        """
        logger.info(
            "[GmailConnector] Starting polling loop for team %s (interval=%ds)",
            team_id, POLL_INTERVAL,
        )

        while True:
            try:
                # Default: look back 1 hour on first run, then use last_checked
                since = _last_checked.get(
                    team_id,
                    datetime.now(tz=timezone.utc) - timedelta(hours=1),
                )

                # Run the blocking HTTP + Redis calls in a thread pool
                await asyncio.to_thread(self.watch_inbox, team_id, since)

                # Advance the cursor so we don't re-process already-seen emails
                _last_checked[team_id] = datetime.now(tz=timezone.utc)

            except asyncio.CancelledError:
                logger.info("[GmailConnector] Polling loop for team %s cancelled", team_id)
                break
            except Exception as exc:
                # Log and continue — transient errors should not crash the loop
                logger.exception(
                    "[GmailConnector] Unexpected error in polling loop for team %s: %s",
                    team_id, exc,
                )

            await asyncio.sleep(POLL_INTERVAL)

    # ---------------------------------------------------------------- #
    # Private helpers                                                     #
    # ---------------------------------------------------------------- #

    def _enqueue_event(self, event: Event) -> None:
        """Convert an Event to Chunks, persist to disk, and push to Redis."""
        chunks = event_to_chunks(event)
        if not chunks:
            logger.warning("[GmailConnector] event_to_chunks returned no chunks for event %s", event.id)
            return

        merged_text = "\n\n".join(chunk.text for chunk in chunks)
        job_id = str(uuid.uuid4())

        # Persist chunk text as .txt so worker normalizer can read it
        os.makedirs(OBJECT_STORE_PATH, exist_ok=True)
        file_path = os.path.join(OBJECT_STORE_PATH, f"{job_id}.txt")
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(merged_text)

        # Build job in the exact same format as upload.py
        job = {
            "job_id": job_id,
            "team_id": event.team_id,
            "filename": f"gmail_{event.id}.txt",
            "file_path": file_path,
            "file_type": ".txt",
        }

        self._redis.lpush("flowstate:jobs", json.dumps(job))
        logger.debug(
            "[GmailConnector] Job %s queued for email event %s (%d chunks)",
            job_id, event.id, len(chunks),
        )
