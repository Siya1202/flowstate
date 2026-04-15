from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

import redis
from fastapi import FastAPI, HTTPException, Request

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_QUEUE_NAME = os.getenv("SLACK_QUEUE_NAME", "flowstate:raw_events")
SLACK_DEFAULT_TEAM_ID = os.getenv("SLACK_TEAM_ID", "team_alpha")

app = FastAPI(title="Flowstate Slack Bot")


def _get_redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL)


def _verify_slack_signature(timestamp: str | None, raw_body: bytes, signature: str | None) -> bool:
    if not SLACK_SIGNING_SECRET:
        return False
    if not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - ts) > 60 * 5:
        return False

    base = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _build_raw_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    event = payload.get("event") or {}
    if event.get("type") != "message":
        return None
    if event.get("bot_id"):
        return None
    if event.get("subtype"):
        return None

    text = str(event.get("text") or "").strip()
    if not text:
        return None

    external_id = event.get("client_msg_id") or event.get("ts") or str(uuid.uuid4())
    team_id = payload.get("team_id") or SLACK_DEFAULT_TEAM_ID

    return {
        "source": "slack",
        "content": text,
        "team_id": team_id,
        "external_id": f"slack:{external_id}",
        "metadata": {
            "channel": event.get("channel"),
            "user": event.get("user"),
            "thread_ts": event.get("thread_ts"),
            "event_ts": event.get("event_ts") or event.get("ts"),
            "raw_type": event.get("type"),
        },
    }


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Slack-Signature")
    timestamp = request.headers.get("X-Slack-Request-Timestamp")

    if not _verify_slack_signature(timestamp, raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    payload = json.loads(raw_body.decode("utf-8") or "{}")

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if payload.get("type") != "event_callback":
        return {"ok": True}

    raw_event = _build_raw_event(payload)
    if raw_event is None:
        return {"ok": True}

    redis_client = _get_redis_client()
    redis_client.lpush(SLACK_QUEUE_NAME, json.dumps(raw_event))
    return {"ok": True}
