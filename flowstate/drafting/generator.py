from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional

import httpx


OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral")


DRAFT_PROMPTS: dict[str, str] = {
    "nudge": (
        "You are a professional assistant helping a team stay unblocked.\n"
        "Task: {title}\n"
        "Owner: {owner}\n"
        "Blocked by: {blocked_by}\n"
        "Blocked by owner: {blocked_by_name}\n"
        "Days stuck: {days_stuck}\n\n"
        "Write a short, polite Slack message to {blocked_by_name} asking for an update. "
        "Do not use filler phrases. Be specific. Max 3 sentences."
    ),
    "deadline_reminder": (
        "Task: {title}\n"
        "Owner: {owner}\n"
        "Due: {deadline} ({hours_remaining}h remaining)\n"
        "Current status: {status}\n\n"
        "Write a brief reminder to {owner} that this task is due soon. "
        "Mention the deadline. Ask for a status update or flag if help is needed."
    ),
}


@dataclass
class Draft:
    task_id: str
    draft_type: str
    body: str
    suggested_recipient: str
    suggested_channel: str
    status: str = "draft"


def generate_draft(task: Any, event: Any, draft_type: str, model: Optional[str] = None) -> Draft:
    prompt_template = DRAFT_PROMPTS.get(draft_type)
    if not prompt_template:
        raise ValueError(f"Unknown draft type: {draft_type}")

    context = _build_context(task, event)
    prompt = prompt_template.format(**context)

    body = _fallback_draft(context, draft_type)
    try:
        response = httpx.post(
            f"{OLLAMA_API_BASE}/api/chat",
            json={
                "model": model or DEFAULT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "").strip()
        if content:
            body = content
    except Exception:
        # Use deterministic fallback so connector flows still work if LLM is unavailable.
        pass

    return Draft(
        task_id=context["task_id"],
        draft_type=draft_type,
        body=body,
        suggested_recipient=context.get("owner") or context.get("blocked_by_name") or "team",
        suggested_channel=context.get("channel", "#flowstate"),
    )


def _build_context(task: Any, event: Any) -> Dict[str, Any]:
    metadata = getattr(event, "metadata", {}) or {}
    title = getattr(task, "title", None) or getattr(task, "task", None) or "Untitled task"
    owner = getattr(task, "owner", None) or metadata.get("owner") or "team"
    deadline = getattr(task, "deadline", None)

    hours_remaining = metadata.get("hours_remaining")
    if hours_remaining is None and deadline:
        parsed_deadline = _to_datetime(deadline)
        if parsed_deadline is not None:
            hours_remaining = max(int((parsed_deadline - datetime.now(timezone.utc)).total_seconds() // 3600), 0)

    return {
        "task_id": str(getattr(task, "id", None) or getattr(task, "task_id", "")),
        "title": str(title),
        "owner": str(owner),
        "blocked_by": metadata.get("blocked_by", "Unknown blocker"),
        "blocked_by_name": metadata.get("blocked_by_name") or metadata.get("blocker_owner", "owner"),
        "days_stuck": int(metadata.get("days_stuck", 1)),
        "deadline": str(deadline) if deadline is not None else "No deadline",
        "hours_remaining": int(hours_remaining) if hours_remaining is not None else 0,
        "status": metadata.get("status") or getattr(task, "status", "open"),
        "channel": metadata.get("channel", "#flowstate"),
    }


def _fallback_draft(context: Dict[str, Any], draft_type: str) -> str:
    if draft_type == "nudge":
        return (
            f"Hi {context['blocked_by_name']}, quick nudge on '{context['title']}'. "
            f"It's currently blocked by '{context['blocked_by']}' and has been stuck for "
            f"{context['days_stuck']} day(s). Could you share a status update?"
        )

    return (
        f"Hi {context['owner']}, reminder that '{context['title']}' is due by {context['deadline']} "
        f"(about {context['hours_remaining']}h remaining). Please share a quick status update "
        "or flag if you need help."
    )


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, str):
        parsed = value.strip()
        if not parsed:
            return None
        if parsed.endswith("Z"):
            parsed = parsed[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(parsed)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    return None