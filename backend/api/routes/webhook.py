"""
webhook.py
POST /webhook — OpenClaw inbound event receiver.

OpenClaw calls this endpoint whenever a connected integration (Gmail, Slack,
Discord, WhatsApp) delivers a new event. The endpoint:

  1. Validates the JSON payload against the WebhookPayload Pydantic schema.
  2. Builds a canonical Event object.
  3. Converts it to Chunks via event_to_chunks().
  4. Pushes a job to the Redis "flowstate:jobs" queue in exactly the same
     format that upload.py uses — so the existing worker.py picks it up
     without any changes.
  5. Returns {"job_id": ..., "status": "queued", "source": ...}.

Security note: In production, add HMAC signature verification using the
OPENCLAW_WEBHOOK_SECRET environment variable before reaching the handler.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from backend.infrastructure.connectors.event_to_chunks import event_to_chunks
from backend.models import Event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])

# ------------------------------------------------------------------ #
# Redis setup                                                           #
# ------------------------------------------------------------------ #

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
OBJECT_STORE_PATH: str = os.getenv("OBJECT_STORE_PATH", "./storage/objects")

_redis_client = redis.from_url(REDIS_URL)

# ------------------------------------------------------------------ #
# Request / Response schemas                                            #
# ------------------------------------------------------------------ #

class WebhookPayload(BaseModel):
    """
    Schema for the JSON body sent by OpenClaw to POST /webhook.

    OpenClaw sends this whenever a connected integration fires an event.
    """

    id: str = Field(..., description="Unique event ID from OpenClaw")
    type: str = Field(
        ...,
        description="Event type: email_received | slack_message | discord_message | whatsapp_message",
    )
    source: str = Field(..., description="Integration source: gmail | slack | discord | whatsapp")
    content: str = Field(..., description="Decoded text content of the event")
    participants: List[str] = Field(default_factory=list, description="Sender + recipients")
    timestamp: datetime = Field(..., description="Event occurrence time (UTC)")
    team_id: str = Field(..., description="Flowstate team identifier")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Original provider payload")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"email_received", "slack_message", "discord_message", "whatsapp_message"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}, got {v!r}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        allowed = {"gmail", "slack", "discord", "whatsapp"}
        if v not in allowed:
            raise ValueError(f"source must be one of {allowed}, got {v!r}")
        return v


class WebhookResponse(BaseModel):
    job_id: str
    status: str
    source: str
    chunks_produced: int


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _persist_chunks_as_file(chunks_text: str, job_id: str) -> str:
    """
    Write the merged chunk text to a temp file in the object store so the
    existing worker.py normalizer can read it like any other uploaded file.

    The worker calls normalize(job["file_path"], job["file_type"]) — we
    write a plain .txt file so the txt normalizer path is used.
    """
    os.makedirs(OBJECT_STORE_PATH, exist_ok=True)
    file_path = os.path.join(OBJECT_STORE_PATH, f"{job_id}.txt")
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(chunks_text)
    return file_path


def _build_redis_job(
    job_id: str,
    team_id: str,
    file_path: str,
    source: str,
    event_id: str,
) -> Dict[str, Any]:
    """
    Build a Redis job dict in the exact same shape as upload.py so worker.py
    can process it without any modifications.
    """
    return {
        "job_id": job_id,
        "team_id": team_id,
        "filename": f"webhook_{source}_{event_id}.txt",
        "file_path": file_path,
        "file_type": ".txt",
    }


# ------------------------------------------------------------------ #
# Endpoint                                                              #
# ------------------------------------------------------------------ #

@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive real-time events from OpenClaw",
    description=(
        "Accepts inbound events from OpenClaw (Gmail, Slack, Discord, WhatsApp), "
        "converts them to Chunks, and enqueues them for processing by the existing "
        "Flowstate pipeline worker."
    ),
)
async def receive_webhook(payload: WebhookPayload) -> WebhookResponse:
    """
    Main webhook handler.

    Steps:
        1. Build a canonical Event from the validated payload.
        2. Convert to Chunks using event_to_chunks().
        3. Merge chunk texts into a single .txt file (worker-compatible).
        4. Push a job to Redis "flowstate:jobs".
        5. Return the job_id so callers can track processing status.
    """
    logger.info(
        "Webhook received: source=%s type=%s event_id=%s team_id=%s",
        payload.source, payload.type, payload.id, payload.team_id,
    )

    # Step 1 — build canonical Event
    event = Event(
        id=payload.id,
        type=payload.type,
        source=payload.source,
        content=payload.content,
        participants=payload.participants,
        timestamp=payload.timestamp,
        team_id=payload.team_id,
        raw=payload.raw,
    )

    # Step 2 — convert to Chunks
    try:
        chunks = event_to_chunks(event)
    except Exception as exc:
        logger.exception("event_to_chunks failed for event %s: %s", payload.id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to convert event to chunks: {exc}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="event_to_chunks produced zero chunks — nothing to enqueue.",
        )

    # Step 3 — merge chunk texts and persist to disk so worker normalizer can read it
    merged_text = "\n\n".join(chunk.text for chunk in chunks)
    job_id = str(uuid.uuid4())

    try:
        file_path = _persist_chunks_as_file(merged_text, job_id)
    except OSError as exc:
        logger.exception("Failed to write chunk file for job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist event content to disk.",
        )

    # Step 4 — push job to Redis in the same format as upload.py
    job = _build_redis_job(
        job_id=job_id,
        team_id=payload.team_id,
        file_path=file_path,
        source=payload.source,
        event_id=payload.id,
    )
    try:
        _redis_client.lpush("flowstate:jobs", json.dumps(job))
    except redis.RedisError as exc:
        logger.exception("Redis push failed for job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue job — Redis unavailable.",
        )

    logger.info(
        "Job %s enqueued for event %s (%d chunks from %s)",
        job_id, payload.id, len(chunks), payload.source,
    )

    # Step 5 — respond
    return WebhookResponse(
        job_id=job_id,
        status="queued",
        source=payload.source,
        chunks_produced=len(chunks),
    )
