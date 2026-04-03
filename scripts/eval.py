import json
import argparse
import httpx
import os
import sys
sys.path.insert(0, ".")
from backend.extraction.extractor import extract_tasks
from backend.preprocessing.normalizer import Chunk

SIMILARITY_THRESHOLD = 0.6

def normalize_title(title: str) -> str:
    return title.lower().strip()

def is_match(extracted: str, ground_truth: str) -> bool:
    e = normalize_title(extracted)
    g = normalize_title(ground_truth)
    return e == g or e in g or g in e

def evaluate_sample(chat: str, ground_truth: list) -> dict:
    chunks = [Chunk(text=line, speaker=None) for line in chat.split("\n") if line.strip()]
    extracted = extract_tasks(chunks)

    extracted_titles = [t.title for t in extracted]
    gt_titles = [t["title"] for t in ground_truth]

    tp = sum(1 for e in extracted_titles if any(is_match(e, g) for g in gt_titles))
    fp = sum(1 for e in extracted_titles if not any(is_match(e, g) for g in gt_titles))
    fn = sum(1 for g in gt_titles if not any(is_match(e, g) for e in extracted_titles))

    return {"tp": tp, "fp": fp, "fn": fn}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="data/synthetic_hackathon.json")
    parser.add_argument("--limit", type=int, default=50, help="Number of samples to evaluate")
    args = parser.parse_args()

    with open(args.dataset) as f:
        dataset = json.load(f)

    dataset = dataset[:args.limit]
    total_tp, total_fp, total_fn = 0, 0, 0

    for i, sample in enumerate(dataset):
        print(f"Evaluating sample {i+1}/{len(dataset)}...")
        result = evaluate_sample(sample["chat"], sample["ground_truth"])
        total_tp += result["tp"]
        total_fp += result["fp"]
        total_fn += result["fn"]

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n{'='*40}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1 Score:  {f1:.3f}")
    print(f"Target:    F1 ≥ 0.90")
    print(f"{'='*40}")
    print(f"{'✅ PASS' if f1 >= 0.90 else '❌ FAIL — needs improvement'}")

if __name__ == "__main__":
    main()