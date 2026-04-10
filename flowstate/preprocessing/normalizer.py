import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
from docx import Document

@dataclass
class Chunk:
    text: str
    speaker: Optional[str] = None
    metadata: Optional[Dict] = None

def normalize(file_path: str, file_type: str) -> List[Chunk]:
    if file_type == ".txt":
        return chunk_whatsapp(file_path)
    elif file_type == ".pdf":
        return extract_pdf_text(file_path)
    elif file_type in [".png", ".jpg"]:
        return extract_image_text(file_path)
    elif file_type == ".docx":
        return extract_docx_text(file_path)
    elif file_type == ".json":
        return parse_discord_json(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

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