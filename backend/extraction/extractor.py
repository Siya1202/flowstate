import httpx
import json
import os
from typing import List, Optional
from dataclasses import dataclass
from backend.preprocessing.normalizer import Chunk

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

@dataclass
class ExtractedTask:
    title: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float = 0.0
    source_snippet: Optional[str] = None
    dependencies: list = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

SYSTEM_PROMPT = """
You are a task extraction assistant. Given a conversation, extract all actionable tasks.
For each task return a JSON array where each item has:
- title: short description of the task
- owner: person responsible (null if unclear)
- deadline: deadline mentioned (null if none)
- confidence: float 0-1 of how confident you are this is a real task
- dependencies: list of other task titles that must be completed before this one (empty list if none)

Example:
[
  {"title": "Design wireframes", "owner": "Alice", "deadline": null, "confidence": 0.9, "dependencies": []},
  {"title": "Build frontend", "owner": "Bob", "deadline": "Friday", "confidence": 0.85, "dependencies": ["Design wireframes"]},
  {"title": "Deploy app", "owner": "Bob", "deadline": "Monday", "confidence": 0.8, "dependencies": ["Build frontend"]}
]

Return ONLY a valid JSON array, no explanation, no markdown.
"""

MAX_CHUNKS = 60
MAX_CHUNK_CHARS = 300

def extract_tasks(chunks: List[Chunk]) -> List[ExtractedTask]:
    filtered = [c for c in chunks if c.text and len(c.text.strip()) > 0]
    capped = [
        Chunk(
            text=c.text[:MAX_CHUNK_CHARS],
            speaker=c.speaker,
            metadata=getattr(c, "metadata", None)
        )
        for c in filtered[:MAX_CHUNKS]
    ]
    conversation = "\n".join(
        [f"{c.speaker}: {c.text}" if c.speaker else c.text for c in capped]
    )

    response = httpx.post(
        f"{OLLAMA_API_BASE}/api/chat",
        json={
            "model": "mistral",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": conversation}
            ],
            "stream": False
        },
        timeout=120.0
    )

    raw = response.json()["message"]["content"]

    try:
        tasks_data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array from response if model added extra text
        start = raw.find("[")
        end = raw.rfind("]") + 1
        tasks_data = json.loads(raw[start:end])

    tasks = []
    for t in tasks_data:
        tasks.append(ExtractedTask(
            title=t.get("title", ""),
            owner=t.get("owner"),
            deadline=t.get("deadline"),
            confidence=t.get("confidence", 0.5),
            source_snippet=None,
            dependencies=t.get("dependencies", [])
))
    return tasks