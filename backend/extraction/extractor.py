from celery import chunks
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
- deadline: ANY time reference mentioned near this task — including dates like "17th", "Friday", "EOD", "tomorrow", "next week", "by end of day", "before the meeting", "kal", "aaj". Convert informal references to a best-guess date. If absolutely no time reference exists, use null.
- confidence: float 0-1 of how confident you are this is a real task
- dependencies: list of other task titles that must be completed before this one (empty list if none)

Be aggressive about finding deadlines — if someone says "kal tak" (by tomorrow), "aaj" (today), "17 tak" (by 17th), treat these as deadlines.

Example:
[
  {"title": "Register for hackathon", "owner": "Malhar", "deadline": "17th March", "confidence": 0.95, "dependencies": []},
  {"title": "Submit presentation", "owner": "Group", "deadline": "EOD Friday", "confidence": 0.9, "dependencies": ["Register for hackathon"]}
]

Return ONLY a valid JSON array, no explanation, no markdown.
"""

MAX_CHUNKS = 60
MAX_CHUNK_CHARS = 300

def extract_tasks(chunks: List[Chunk]) -> List[ExtractedTask]:
    all_tasks = []
    batch_size = 100

    chunks = chunks[:1000]  # Cap at 1000 chunks for performance
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        conversation = "\n".join(
            [f"{c.speaker}: {c.text}" if c.speaker else c.text for c in batch]
        )

        print(f"  Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}...")

        try:
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
                start = raw.find("[")
                end = raw.rfind("]") + 1
                if start != -1 and end > start:
                    tasks_data = json.loads(raw[start:end])
                else:
                    print(f"  ⚠️ Batch {i//batch_size + 1} returned invalid JSON, skipping")
                    continue

            for t in tasks_data:
                all_tasks.append(ExtractedTask(
                    title=t.get("title", ""),
                    owner=t.get("owner"),
                    deadline=t.get("deadline"),
                    confidence=t.get("confidence", 0.5),
                    source_snippet=None,
                    dependencies=t.get("dependencies", [])
                ))

        except Exception as e:
            print(f"  ⚠️ Batch {i//batch_size + 1} failed: {e}, skipping")
            continue

    return all_tasks