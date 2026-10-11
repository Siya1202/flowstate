"""
event_to_chunks.py
Converts a real-time Event into one or more Chunk objects that the existing
Flowstate pipeline (normalize → extract → enrich → DAG → governance → calendar)
can process without any modifications.

Splitting strategy:
  - email_received: split body by paragraph (double newline). Each paragraph
    becomes its own Chunk so the extractor can reason about individual action
    items independently.
  - slack_message / discord_message / whatsapp_message: one Chunk per event
    (messages are typically short enough to be atomic).
  - fallback: one Chunk containing the full content.

Speaker and source metadata are preserved so the enrichment and governance
stages can infer ownership and trace tasks back to their origin event.
"""

from __future__ import annotations

import logging
from typing import List

from backend.models import Chunk, Event

logger = logging.getLogger(__name__)


def event_to_chunks(event: Event) -> List[Chunk]:
    """
    Convert an Event into a list of Chunks consumable by the existing pipeline.

    Args:
        event: A normalised Event from any connector (Gmail, Slack, Discord, …).

    Returns:
        One or more Chunk objects with:
            - text       — the message content (or paragraph slice for emails)
            - speaker    — the first participant (sender / author)
            - source_ref — "<source>/<event_id>" for full traceability
            - timestamp  — the event timestamp
    """
    chunks: List[Chunk] = []

    # Derive a stable source_ref so tasks can be traced back to the event
    source_ref = f"{event.source}/{event.id}"

    # The "speaker" is the primary sender — first participant if available
    speaker = event.participants[0] if event.participants else None

    if event.type == "email_received":
        chunks = _split_email(event, source_ref, speaker)
    elif event.type in {"slack_message", "discord_message", "whatsapp_message"}:
        chunks = _single_chunk(event, source_ref, speaker)
    else:
        # Generic fallback — treat the whole content as one chunk
        logger.debug(
            "event_to_chunks: unknown event type %r, falling back to single chunk", event.type
        )
        chunks = _single_chunk(event, source_ref, speaker)

    logger.info(
        "event_to_chunks: event %s (%s) → %d chunk(s)",
        event.id, event.type, len(chunks),
    )
    return chunks


# ------------------------------------------------------------------ #
# Private helpers                                                       #
# ------------------------------------------------------------------ #

def _split_email(event: Event, source_ref: str, speaker: str | None) -> List[Chunk]:
    """
    Split an email body into paragraph-level chunks.

    Paragraphs are delimited by one or more blank lines. Very short fragments
    (e.g. salutations like "Hi Bob,") are merged into the next paragraph to
    avoid generating useless chunks with no extractable tasks.
    """
    raw_paragraphs = [p.strip() for p in event.content.split("\n\n")]

    # Filter out whitespace-only paragraphs; merge fragments < 20 chars
    merged: List[str] = []
    buffer = ""
    for para in raw_paragraphs:
        if not para:
            continue
        if len(para) < 20 and not para.endswith((".", "!", "?")):
            # Likely a salutation or one-liner — keep accumulating
            buffer = f"{buffer} {para}".strip() if buffer else para
        else:
            if buffer:
                para = f"{buffer} {para}".strip()
                buffer = ""
            merged.append(para)

    # Flush any remaining buffer
    if buffer:
        merged.append(buffer)

    # If nothing survived the filter, fall back to the full content
    if not merged:
        merged = [event.content.strip() or "(empty email)"]

    return [
        Chunk(
            text=para,
            speaker=speaker,
            source_ref=source_ref,
            timestamp=event.timestamp,
        )
        for para in merged
    ]


def _single_chunk(event: Event, source_ref: str, speaker: str | None) -> List[Chunk]:
    """Return a single Chunk containing the complete event content."""
    content = event.content.strip() or "(empty message)"
    return [
        Chunk(
            text=content,
            speaker=speaker,
            source_ref=source_ref,
            timestamp=event.timestamp,
        )
    ]
