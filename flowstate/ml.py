import time

from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"

print(f"[ml] Loading SentenceTransformer model '{_MODEL_NAME}'...")
_t0 = time.perf_counter()
model = SentenceTransformer(_MODEL_NAME)
_elapsed = time.perf_counter() - _t0
print(f"[ml] Model loaded in {_elapsed:.2f}s")

__all__ = ["model"]