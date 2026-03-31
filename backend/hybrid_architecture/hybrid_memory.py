import os
import psycopg2
import chromadb
import boto3
import logging
from typing import Dict, List, Optional

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
DB_NAME = os.getenv("POSTGRES_DB", "flowstate")
DB_USER = os.getenv("POSTGRES_USER", "flowstate_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "your_password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_BUCKET = os.getenv("S3_BUCKET", "flowstate-bucket")

# --- PostgreSQL ---
def save_to_postgres(task: Dict) -> bool:
    """Save task to PostgreSQL. Returns True if successful."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (task_text, confidence, owner, inferred_owner, duplicate_candidates)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                task["task"],
                task["confidence"],
                task.get("owner"),
                task.get("inferred_owner"),
                task.get("duplicate_candidates", [])
            )
        )
        conn.commit()
        logger.info(f"Saved task to PostgreSQL: {task['task']}")
        return True
    except Exception as e:
        logger.error(f"Error saving to PostgreSQL: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

# --- ChromaDB ---
def save_embedding(task: Dict, embedding: List[float]) -> bool:
    """Save task embedding to ChromaDB. Returns True if successful."""
    try:
        client = chromadb.HttpClient(host=DB_HOST, port=8000)
        collection = client.get_or_create_collection("task_embeddings")
        collection.add(
            embeddings=[embedding],
            documents=[task["task"]],
            ids=[str(task["id"])]
        )
        logger.info(f"Saved embedding for task: {task['task']}")
        return True
    except Exception as e:
        logger.error(f"Error saving to ChromaDB: {e}")
        return False

# --- Object Store ---
def upload_to_s3(file_path: str, object_key: str) -> bool:
    """Upload file to S3-compatible object store. Returns True if successful."""
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        )
        s3.upload_file(file_path, S3_BUCKET, object_key)
        logger.info(f"Uploaded {file_path} to S3 as {object_key}")
        return True
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        return False

# --- Example Usage ---
if __name__ == "__main__":
    example_task = {
        "id": 1,
        "task": "Implement AI governance layer",
        "confidence": 0.95,
        "owner": "srishti",
        "inferred_owner": None,
        "duplicate_candidates": []
    }
    example_embedding = [0.1, 0.2, 0.3]  # Replace with actual embedding

    save_to_postgres(example_task)
    save_embedding(example_task, example_embedding)
    upload_to_s3("example.txt", "tasks/example.txt")