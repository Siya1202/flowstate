"""
openclaw/client.py
Concrete ConnectorAdapter that proxies all calls through the OpenClaw API.

OpenClaw is an integration middleware that exposes a unified REST API over
Gmail, Slack, Discord, WhatsApp, and calendar providers. This client handles:
  - Authentication via OPENCLAW_API_KEY header
  - HTTP transport via httpx (sync) for simplicity inside background tasks
  - Normalisation of OpenClaw response payloads into canonical Event objects
  - Structured error handling with retries for transient failures

Environment variables (loaded at import time via python-dotenv / os.getenv):
    OPENCLAW_API_BASE  — base URL, e.g. https://api.openclaw.io/v1
    OPENCLAW_API_KEY   — bearer token for the OpenClaw account
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from backend.infrastructure.connectors.connector_adapter import ConnectorAdapter
from backend.models import Event

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Config                                                                #
# ------------------------------------------------------------------ #

_BASE_URL: str = os.getenv("OPENCLAW_API_BASE", "https://api.openclaw.io/v1").rstrip("/")
_API_KEY: str = os.getenv("OPENCLAW_API_KEY", "")

# httpx transport settings
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 3


# ------------------------------------------------------------------ #
# Helpers                                                               #
# ------------------------------------------------------------------ #

def _parse_ts(ts: Any) -> datetime:
    """Parse an ISO-8601 string or Unix timestamp into a timezone-aware datetime."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    raise ValueError(f"Cannot parse timestamp: {ts!r}")


def _default_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


class OpenClawError(Exception):
    """Raised when the OpenClaw API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"OpenClaw API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


# ------------------------------------------------------------------ #
# Client                                                                #
# ------------------------------------------------------------------ #

class OpenClawClient(ConnectorAdapter):
    """
    HTTP client for the OpenClaw connector API.

    Usage::

        client = OpenClawClient()
        emails = client.get_emails(since=datetime(2024, 1, 1, tzinfo=timezone.utc))
    """

    def __init__(self, team_id: str = "") -> None:
        self.team_id = team_id
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers=_default_headers(),
            timeout=_TIMEOUT,
        )

    # ---------------------------------------------------------------- #
    # Internal HTTP helpers                                              #
    # ---------------------------------------------------------------- #

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        """Execute a GET with basic retry logic for 5xx / network errors."""
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._client.get(path, params=params)
                self._raise_for_status(resp)
                return resp.json()
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning(
                    "OpenClaw GET %s attempt %d/%d failed: %s",
                    path, attempt, _MAX_RETRIES, exc,
                )
            except OpenClawError:
                raise  # don't retry 4xx errors
        raise RuntimeError(f"OpenClaw GET {path} failed after {_MAX_RETRIES} attempts") from last_exc

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        """Execute a POST with basic retry logic for 5xx / network errors."""
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._client.post(path, json=payload)
                self._raise_for_status(resp)
                return resp.json()
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning(
                    "OpenClaw POST %s attempt %d/%d failed: %s",
                    path, attempt, _MAX_RETRIES, exc,
                )
            except OpenClawError:
                raise
        raise RuntimeError(f"OpenClaw POST {path} failed after {_MAX_RETRIES} attempts") from last_exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_error:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise OpenClawError(resp.status_code, detail)

    # ---------------------------------------------------------------- #
    # Read operations (ConnectorAdapter interface)                       #
    # ---------------------------------------------------------------- #

    def get_emails(self, since: datetime) -> List[Event]:
        """
        Fetch emails from the OpenClaw /gmail/messages endpoint.

        OpenClaw response schema (array of objects)::

            {
              "id": "msg_abc123",
              "subject": "Project kickoff",
              "from": "alice@example.com",
              "to": ["bob@example.com"],
              "body": "Hi Bob, …",
              "received_at": "2024-06-01T09:00:00Z",
              "raw": { … }
            }
        """
        logger.info("Fetching emails from OpenClaw since %s", since.isoformat())
        data = self._get(
            "/gmail/messages",
            params={"since": since.isoformat(), "team_id": self.team_id or None},
        )
        messages: List[Dict[str, Any]] = data if isinstance(data, list) else data.get("messages", [])

        events: List[Event] = []
        for msg in messages:
            participants = [msg.get("from", "")] + (msg.get("to") or [])
            event = Event(
                id=msg.get("id", str(uuid.uuid4())),
                type="email_received",
                source="gmail",
                content=f"Subject: {msg.get('subject', '')}\n\n{msg.get('body', '')}",
                participants=[p for p in participants if p],
                timestamp=_parse_ts(msg.get("received_at", datetime.now(tz=timezone.utc).isoformat())),
                team_id=self.team_id,
                raw=msg,
            )
            events.append(event)

        logger.info("Fetched %d email events", len(events))
        return events

    def get_slack_messages(self, channel: str, since: datetime) -> List[Event]:
        """
        Fetch Slack messages from the OpenClaw /slack/messages endpoint.

        OpenClaw response schema (array of objects)::

            {
              "id": "slack_123",
              "channel": "C0123ABCD",
              "user": "U0123ABCD",
              "username": "alice",
              "text": "Let's sync at 3pm",
              "ts": "1717233600.000000",
              "raw": { … }
            }
        """
        logger.info("Fetching Slack messages for channel %s since %s", channel, since.isoformat())
        data = self._get(
            "/slack/messages",
            params={
                "channel": channel,
                "since": since.isoformat(),
                "team_id": self.team_id or None,
            },
        )
        messages: List[Dict[str, Any]] = data if isinstance(data, list) else data.get("messages", [])

        events: List[Event] = []
        for msg in messages:
            event = Event(
                id=msg.get("id", str(uuid.uuid4())),
                type="slack_message",
                source="slack",
                content=msg.get("text", ""),
                participants=[msg.get("username") or msg.get("user", "unknown")],
                timestamp=_parse_ts(msg.get("ts", datetime.now(tz=timezone.utc).timestamp())),
                team_id=self.team_id,
                raw=msg,
            )
            events.append(event)

        logger.info("Fetched %d Slack message events for channel %s", len(events), channel)
        return events

    # ---------------------------------------------------------------- #
    # Write / action operations (ConnectorAdapter interface)            #
    # ---------------------------------------------------------------- #

    def send_email(self, to: str, subject: str, body: str) -> None:
        """
        Send an email via OpenClaw /gmail/send.

        OpenClaw request body::

            {"to": "...", "subject": "...", "body": "..."}
        """
        logger.info("Sending email to %s via OpenClaw (subject: %r)", to, subject)
        self._post("/gmail/send", {"to": to, "subject": subject, "body": body})
        logger.debug("Email to %s sent successfully", to)

    def create_calendar_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """
        Create a Google Calendar event via OpenClaw /calendar/events.

        OpenClaw request body::

            {"title": "...", "start": "ISO-8601", "end": "ISO-8601", "team_id": "..."}
        """
        logger.info("Creating calendar event %r from %s to %s", title, start.isoformat(), end.isoformat())
        self._post(
            "/calendar/events",
            {
                "title": title,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "team_id": self.team_id,
            },
        )
        logger.debug("Calendar event %r created successfully", title)

    # ---------------------------------------------------------------- #
    # Lifecycle                                                          #
    # ---------------------------------------------------------------- #

    def close(self) -> None:
        """Release the underlying httpx connection pool."""
        self._client.close()

    def __enter__(self) -> "OpenClawClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
