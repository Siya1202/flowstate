import chromadb
import os
from functools import lru_cache
from typing import List, Optional
from backend.models import Task

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

@lru_cache(maxsize=128)
def get_or_create_collection(team_id: str):
    return client.get_or_create_collection(name=f"tasks_{team_id}")

def store_task(task: Task, embedding: List[float]):
    """Store a task and its embedding in ChromaDB."""
    collection = get_or_create_collection(task.team_id)
    collection.upsert(
        ids=[task.task_id or task.task],
        embeddings=[embedding],
        documents=[task.task],
        metadatas=[{
            "owner": task.owner or "",
            "deadline": task.deadline or "",
            "confidence": str(task.confidence),
            "source_ref": task.source_ref,
            "team_id": task.team_id
        }]
    )

def store_tasks_batch(tasks: List[Task], embeddings: List[List[float]]):
    """Batch upsert a list of tasks and their embeddings into ChromaDB."""
    if not tasks:
        return
    # Group tasks by team_id so each collection is touched once per team
    from collections import defaultdict
    groups: defaultdict[str, list] = defaultdict(list)
    for task, embedding in zip(tasks, embeddings):
        groups[task.team_id].append((task, embedding))

    for team_id, items in groups.items():
        collection = get_or_create_collection(team_id)
        collection.upsert(
            ids=[t.task_id or t.task for t, _ in items],
            embeddings=[emb for _, emb in items],
            documents=[t.task for t, _ in items],
            metadatas=[{
                "owner": t.owner or "",
                "deadline": t.deadline or "",
                "confidence": str(t.confidence),
                "source_ref": t.source_ref,
                "team_id": t.team_id
            } for t, _ in items]
        )

def query_similar_tasks(team_id: str, embedding: List[float], top_k: int = 3) -> List[dict]:
    """Query ChromaDB for similar tasks."""
    collection = get_or_create_collection(team_id)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k
    )
    return results