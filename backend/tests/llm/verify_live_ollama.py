"""Live end-to-end verification against the local Ollama daemon.

NOT mocked. Calls the real OllamaClient at http://127.0.0.1:11434 with the
locally-installed model (default: mistral), feeds MOCK_RETRIEVAL_RESULTS to
bypass the retriever, runs ResponseGenerator.generate() with realistic
queries, and inspects the ACTUAL JSON the LLM returns.

What this proves that the mocked harness cannot:
  - Whether the real LLM emits movie_id as int or str (the smoking-gun
    hypothesis for the production 100% fallback rate)
  - That ResponseGenerator's int->str coercion handles whatever the live
    model actually produces
  - That the full prompt template renders, json.loads succeeds, and every
    field of every recommendation is populated and distinct

Usage:
  PYTHONIOENCODING=utf-8 python backend/tests/llm/verify_live_ollama.py
Optional env:
  OLLAMA_BASE_URL (default http://127.0.0.1:11434)
  OLLAMA_MODEL    (default mistral)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests

from backend.rag.generator import ResponseGenerator
from backend.rag.llm_client import OllamaClient
from backend.tests.llm.mock_data import MOCK_RETRIEVAL_RESULTS


BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "mistral")

CANDIDATES_BY_ID = {m["movie_id"]: m for m in MOCK_RETRIEVAL_RESULTS}


QUERIES = [
    {
        "user_message": "Character-driven dramas from the 2010s with bittersweet endings",
        "intent": {
            "intent": "find_by_mood",
            "reference_movie": None,
            "attributes": {
                "genre": "drama",
                "mood": "bittersweet",
                "era": "2010s",
                "exclusions": None,
            },
            "refinement": None,
        },
    },
    {
        "user_message": "Movies about memory and love",
        "intent": {
            "intent": "find_by_mood",
            "reference_movie": None,
            "attributes": {
                "genre": None,
                "mood": "thoughtful",
                "era": None,
                "exclusions": None,
            },
            "refinement": None,
        },
    },
    {
        "user_message": "Mind-bending sci-fi with emotional depth",
        "intent": {
            "intent": "find_by_mood",
            "reference_movie": None,
            "attributes": {
                "genre": "science fiction",
                "mood": "emotional",
                "era": None,
                "exclusions": None,
            },
            "refinement": None,
        },
    },
]


def banner(text: str, width: int = 78) -> None:
    print()
    print("=" * width)
    print(text)
    print("=" * width)


def preflight() -> None:
    banner(f"PREFLIGHT - Ollama at {BASE_URL}, model {MODEL!r}")
    r = requests.get(f"{BASE_URL}/api/tags", timeout=10)
    r.raise_for_status()
    tags = r.json().get("models", [])
    names = [t["name"] for t in tags]
    print(f"  available models: {names}")
    if not any(MODEL in n or n.startswith(MODEL + ":") for n in names):
        print(f"  WARNING: requested model {MODEL!r} not in tag list; will rely on Ollama's name resolution")


def field_checks(rec: dict, idx: int) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    mid = rec.get("movie_id")
    checks.append((f"[{idx}] movie_id is str", isinstance(mid, str), f"type={type(mid).__name__} value={mid!r}"))
    checks.append((f"[{idx}] movie_id resolves to a real candidate", mid in CANDIDATES_BY_ID, f"id={mid!r}"))
    source = CANDIDATES_BY_ID.get(mid) or {}
    title = rec.get("title")
    checks.append((f"[{idx}] title matches source", title == source.get("title"), f"got={title!r}"))
    year = rec.get("year")
    checks.append((f"[{idx}] year matches source", year == source.get("year"), f"got={year!r}"))
    genres = rec.get("genres")
    checks.append((f"[{idx}] genres matches source", genres == list(source.get("genres", [])), f"got={genres!r}"))
    explanation = rec.get("explanation") or ""
    plot_full = source.get("plot_summary", "")
    plot_preview = rec.get("plot_preview", "")
    checks.append((f"[{idx}] explanation non-empty", isinstance(explanation, str) and len(explanation.strip()) > 0, f"len={len(explanation)}"))
    checks.append((f"[{idx}] explanation != plot_preview", explanation != plot_preview, "ok" if explanation != plot_preview else "EQUAL"))
    checks.append((f"[{idx}] explanation NOT substring of plot", not (explanation and explanation in plot_full), "ok" if explanation not in plot_full else "SUBSTRING"))
    checks.append((f"[{idx}] plot_preview equals plot_summary[:300]", plot_preview == plot_full[:300], f"len={len(plot_preview)}"))
    mr = rec.get("match_reasons")
    checks.append((f"[{idx}] match_reasons is list[str]", isinstance(mr, list) and all(isinstance(x, str) for x in mr), f"value={mr!r}"))
    return checks


def run_query(client: OllamaClient, q: dict) -> tuple[bool, dict, dict]:
    """Run one real query and return (all_passed, generator_output, llm_raw_first_call)."""
    user_msg = q["user_message"]
    intent = q["intent"]

    banner(f"QUERY: {user_msg!r}")
    print(f"  intent.attributes: {intent['attributes']}")

    # Capture the raw LLM JSON output BEFORE any validation, to see what
    # type movie_id actually arrives as. We do this by calling generate_json
    # ourselves first against the same prompt the generator would build.
    from backend.rag._prompt_loader import load_prompt
    from backend.rag.generator import _render_candidates, _render_history

    template = load_prompt("generation_recommend")
    base_prompt = template.format(
        user_message=user_msg,
        intent=intent.get("intent", "find_by_mood"),
        conversation_history=_render_history(None),
        candidates_block=_render_candidates(MOCK_RETRIEVAL_RESULTS),
    )

    t0 = time.time()
    raw = client.generate_json(base_prompt)
    t1 = time.time()

    print(f"  raw LLM call took {t1 - t0:.1f}s")
    print(f"  raw LLM JSON keys: {list(raw.keys())}")
    if "picks" in raw:
        for i, p in enumerate(raw.get("picks", [])):
            pid = p.get("movie_id")
            print(f"    raw_pick[{i}]: movie_id={pid!r} type={type(pid).__name__}  explanation_preview={(p.get('explanation') or '')[:90]!r}")
    elif "error" in raw:
        print(f"    raw LLM ERROR: {raw['error']}  raw_response_snippet={raw.get('raw_response', '')[:200]!r}")

    # Now run the full generator (it will make its own call(s), but we've
    # already seen the prompt-level behavior above).
    gen = ResponseGenerator(client)
    t2 = time.time()
    out = gen.generate(user_msg, MOCK_RETRIEVAL_RESULTS, intent)
    t3 = time.time()
    print(f"  generator end-to-end took {t3 - t2:.1f}s")
    print(f"  response_text: {out.get('response_text', '')!r}")
    print(f"  num_recommendations: {len(out.get('recommendations', []))}")

    all_checks: list[tuple[str, bool, str]] = []
    rt = out.get("response_text")
    all_checks.append(("response_text non-empty", isinstance(rt, str) and len(rt.strip()) > 0, f"len={len(rt or '')}"))
    recs = out.get("recommendations", [])
    all_checks.append(("recommendations is list", isinstance(recs, list), f"type={type(recs).__name__}"))
    if len(recs) >= 2:
        explanations = [r["explanation"] for r in recs]
        distinct = len(set(explanations)) == len(explanations)
        all_checks.append(("explanations distinct across cards", distinct, f"{len(set(explanations))} unique of {len(explanations)}"))
    for i, rec in enumerate(recs):
        print(f"\n  [{i}] movie_id={rec.get('movie_id')!r} title={rec.get('title')!r} year={rec.get('year')}")
        print(f"      genres={rec.get('genres')}")
        print(f"      explanation: {rec.get('explanation')!r}")
        print(f"      plot_preview len={len(rec.get('plot_preview', ''))}  preview60={rec.get('plot_preview', '')[:60]!r}")
        print(f"      match_reasons: {rec.get('match_reasons')}")
        all_checks.extend(field_checks(rec, i))

    print(f"\n  CHECKS:")
    all_passed = True
    for label, ok, detail in all_checks:
        marker = "PASS" if ok else "FAIL"
        print(f"    [{marker}] {label}  ({detail})")
        if not ok:
            all_passed = False
    return all_passed, out, raw


def main() -> int:
    preflight()
    client = OllamaClient(base_url=BASE_URL, model=MODEL)

    results = []
    for q in QUERIES:
        passed, _, _ = run_query(client, q)
        results.append((q["user_message"], passed))

    banner("SUMMARY")
    all_ok = True
    for name, ok in results:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {name}")
        if not ok:
            all_ok = False
    print(f"\n  Overall: {'ALL PASS' if all_ok else 'FAILURES PRESENT'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
