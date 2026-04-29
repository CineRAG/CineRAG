"""
scripts/evaluate_retrieval.py
Offline retrieval evaluation — MRR@5 and NDCG@5.

Compares: dense-only vs bm25-only vs hybrid (RRF).
Writes results to data/eval/results.json.

Run from project root:
    python scripts/evaluate_retrieval.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from config import QUERIES_PATH, RESULTS_PATH

TOP_K = 5


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------

def mrr_at_k(ranked_ids: list[str], relevant: set[str], k: int = 5) -> float:
    for rank, mid in enumerate(ranked_ids[:k], start=1):
        if mid in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], k: int = 5) -> float:
    dcg  = sum(1.0 / np.log2(r + 1) for r, mid in enumerate(ranked_ids[:k], start=1) if mid in relevant)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / idcg if idcg > 0 else 0.0


# ------------------------------------------------------------------
# Evaluation runner
# ------------------------------------------------------------------

def evaluate(retriever, queries: list[dict], method: str) -> dict:
    fn = {
        "dense":  lambda q: retriever.retrieve_dense(q, top_k=TOP_K),
        "sparse": lambda q: retriever.retrieve_sparse(q, top_k=TOP_K),
        "hybrid": lambda q: retriever.retrieve_hybrid(q, top_k=TOP_K),
    }[method]

    per_query, mrr_scores, ndcg_scores = [], [], []

    for item in queries:
        relevant   = set(item["expected_movie_ids"])
        results    = fn(item["query"])
        ranked_ids = [r["movie_id"] for r in results]

        mrr  = mrr_at_k(ranked_ids, relevant, TOP_K)
        ndcg = ndcg_at_k(ranked_ids, relevant, TOP_K)
        mrr_scores.append(mrr)
        ndcg_scores.append(ndcg)

        per_query.append({
            "query_id":    item["query_id"],
            "query":       item["query"],
            "expected_ids":list(relevant),
            "ranked_ids":  ranked_ids,
            "mrr":         round(mrr, 4),
            "ndcg":        round(ndcg, 4),
            "hit":         mrr > 0,
        })

    return {
        "method":    method,
        "mrr_at_5":  round(float(np.mean(mrr_scores)), 4),
        "ndcg_at_5": round(float(np.mean(ndcg_scores)), 4),
        "num_queries": len(queries),
        "num_hits":  sum(1 for q in per_query if q["hit"]),
        "per_query": per_query,
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    if not QUERIES_PATH.exists():
        print(f"ERROR: {QUERIES_PATH} not found.")
        sys.exit(1)

    with open(QUERIES_PATH, encoding="utf-8") as f:
        queries = json.load(f)
    print(f"Loaded {len(queries)} queries.")

    print("Loading MovieRetriever...")
    from rag.retriever import MovieRetriever
    retriever = MovieRetriever()

    all_results = []
    for method in ("dense", "sparse", "hybrid"):
        print(f"\nEvaluating [{method}]...")
        t0     = time.time()
        result = evaluate(retriever, queries, method)
        elapsed = time.time() - t0
        print(f"  MRR@5  = {result['mrr_at_5']:.4f}")
        print(f"  NDCG@5 = {result['ndcg_at_5']:.4f}")
        print(f"  Hits   = {result['num_hits']}/{result['num_queries']}")
        print(f"  Time   = {elapsed:.1f}s")
        all_results.append(result)

    print("\n" + "=" * 46)
    print(f"{'Method':<10} {'MRR@5':>8} {'NDCG@5':>8} {'Hits':>8}")
    print("-" * 46)
    for r in all_results:
        print(f"{r['method']:<10} {r['mrr_at_5']:>8.4f} {r['ndcg_at_5']:>8.4f} {r['num_hits']:>5}/{r['num_queries']}")
    print("=" * 46)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "eval_date":   time.strftime("%Y-%m-%dT%H:%M:%S"),
        "top_k":       TOP_K,
        "num_queries": len(queries),
        "results":     all_results,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
