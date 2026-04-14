import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
from docx import Document
from flowstate.watchers.base import RawEvent

@dataclass
class Chunk:
    text: str
    speaker: Optional[str] = None
    metadata: Optional[Dict] = None

def normalize(
    file_path: Optional[str] = None,
    file_type: Optional[str] = None,
    *,
    content: Optional[str] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> List[Chunk]:
    # New watcher path: normalize already-extracted raw text payloads.
    if content is not None:
        return normalize_raw_content(content=content, source=source, metadata=metadata or {})

    if not file_path or not file_type:
        raise ValueError("Either content or (file_path and file_type) must be provided")

    if file_type == ".txt":
        return chunk_whatsapp(file_path)
    elif file_type == ".pdf":
        return extract_pdf_text(file_path)
    elif file_type in [".png", ".jpg", ".jpeg"]:
        return extract_image_text(file_path)
    elif file_type == ".docx":
        return extract_docx_text(file_path)
    elif file_type == ".json":
        return parse_discord_json(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def normalize_raw_event(event: RawEvent) -> List[Chunk]:
    """Convert any RawEvent into Chunks for the extraction pipeline."""
    return normalize(
        content=event.content,
        source=event.source,
        metadata={**event.metadata, "team_id": event.team_id},
    )


def normalize_raw_content(content: str, source: Optional[str], metadata: Dict) -> List[Chunk]:
    speaker = metadata.get("sender") or metadata.get("from")
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    if source in {"slack", "discord", "whatsapp"} and len(lines) > 1:
        return [Chunk(text=line, speaker=speaker, metadata=metadata) for line in lines]

    return [Chunk(text=content.strip(), speaker=speaker, metadata=metadata)] if content.strip() else []

def chunk_whatsapp(file_path: str) -> List[Chunk]:
    chunks = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                speaker = parts[1].strip()
                text = parts[2].strip()
                chunks.append(Chunk(text=text, speaker=speaker))
    return chunks

def extract_pdf_text(file_path: str) -> List[Chunk]:
    chunks = []
    with open(file_path, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                chunks.append(Chunk(text=text))
    return chunks

def extract_image_text(file_path: str) -> List[Chunk]:
    text = pytesseract.image_to_string(Image.open(file_path))
    return [Chunk(text=text)]

def extract_docx_text(file_path: str) -> List[Chunk]:
    doc = Document(file_path)
    chunks = [Chunk(text=para.text) for para in doc.paragraphs if para.text.strip()]
    return chunks

def parse_discord_json(file_path: str) -> List[Chunk]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = []
    for message in data.get("messages", []):
        chunks.append(Chunk(
            text=message.get("content", ""),
            speaker=message.get("author", {}).get("name", None)
        ))
    return chunks