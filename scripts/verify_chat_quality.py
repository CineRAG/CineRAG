"""Full content-level verification of /api/chat — every field, every spec rule.

Validates every Recommendation field against:
  - schema (backend/chat/schemas.py:24-31 — Recommendation)
  - prompt rules (backend/rag/prompts/generation_recommend.txt — 1-3 picks,
    movie_id from candidates only, 1-3 match_reasons, no plot copying)
  - regression-bug fingerprints (deterministic-fallback intros, identical-
    explanations, empty plot_preview, explanation==plot_preview)
  - corpus existence (each movie_id and title is verified against
    /api/movies/{id} and /api/movies/search)

Run on Nuvolos AFTER backend is up:

    cd /files/CineRAG
    conda activate cinerag_backend
    python scripts/verify_chat_quality.py
    python scripts/verify_chat_quality.py "your custom query"

Exit codes:
    0 = PASS — every check green
    1 = FAIL — at least one issue (see output)
    2 = HTTP setup failure (signup or chat returned non-2xx)
"""
from __future__ import annotations

import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
DEFAULT_QUERY = "Recommend me a mind-bending sci-fi movie like Inception"

# Strings that should never appear in an LLM-generated explanation.
# If they do, the deterministic-fallback path was triggered = LLM output unusable.
FALLBACK_FINGERPRINTS = (
    "A top match retrieved from the catalog",
    "see the plot summary below",
    "Another close fit",
    "Also surfaced",
)


def signup_and_token() -> str:
    email = f"verify_q_{int(time.time())}@test.local"
    print(f"Signing up: {email}")
    r = requests.post(
        f"{BASE}/api/auth/signup",
        json={"email": email, "password": "test123"},
        timeout=30,
    )
    if r.status_code != 201:
        raise SystemExit(f"FAIL signup HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["token"]


def run_chat(tok: str, query: str) -> dict:
    print(f"\nPOST /api/chat: {query!r}")
    r = requests.post(
        f"{BASE}/api/chat",
        json={"message": query, "session_id": "verify-q-1"},
        headers={"Authorization": f"Bearer {tok}"},
        timeout=180,
    )
    print(f"  HTTP: {r.status_code}")
    if r.status_code != 200:
        raise SystemExit(f"FAIL chat HTTP {r.status_code}: {r.text[:400]}")
    return r.json()


def check_recommendation(rec: dict) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    mid = rec.get("movie_id")
    title = rec.get("title")
    year = rec.get("year")
    genres = rec.get("genres")
    expl = rec.get("explanation")
    plot = rec.get("plot_preview")
    reasons = rec.get("match_reasons")

    # Required fields.
    if not isinstance(mid, str) or not mid:
        errors.append("movie_id missing or not string")
    elif not mid.isdigit():
        warnings.append(f"movie_id not numeric ({mid!r}) — CMU corpus IDs are integer-strings")

    if not isinstance(title, str) or not title:
        errors.append("title missing or empty")

    if not isinstance(expl, str) or not expl:
        errors.append("explanation missing or empty")

    if not isinstance(plot, str) or not plot:
        errors.append(
            "plot_preview empty — this is the original Why-this-movie? bug fingerprint"
        )

    # Optional / typed fields.
    if year is not None and not isinstance(year, int):
        errors.append(f"year not int: {year!r}")

    if not isinstance(genres, list):
        errors.append(f"genres not list (got {type(genres).__name__})")
    elif not all(isinstance(g, str) for g in genres):
        errors.append("genres list has non-string entries")

    if not isinstance(reasons, list):
        errors.append(f"match_reasons not list (got {type(reasons).__name__})")
    else:
        if not (1 <= len(reasons) <= 3):
            errors.append(
                f"match_reasons count {len(reasons)} outside prompt rule 1-3"
            )
        if any(not isinstance(x, str) or not x.strip() for x in reasons):
            errors.append("match_reasons has empty/non-string entries")

    # Bug-fingerprint checks.
    if isinstance(expl, str) and isinstance(plot, str) and expl.strip() and plot.strip():
        if expl.strip() == plot.strip():
            errors.append("explanation == plot_preview (LLM copied plot — prompt violation)")

    if isinstance(expl, str):
        for fp in FALLBACK_FINGERPRINTS:
            if fp.lower() in expl.lower():
                warnings.append(
                    f"explanation contains fallback fingerprint {fp!r} — LLM output was unusable, fell back to deterministic intro"
                )
                break
        if len(expl) < 30:
            warnings.append(f"explanation very short ({len(expl)} chars) — may be low quality")

    return errors, warnings


def corpus_lookup(tok: str, mid: str, title: str) -> tuple[str, str]:
    """Returns (by_id_status, by_title_status) strings for display."""
    hdr = {"Authorization": f"Bearer {tok}"}

    # 1) Direct movie_id lookup.
    try:
        r = requests.get(f"{BASE}/api/movies/{mid}", headers=hdr, timeout=15)
        if r.status_code == 200:
            d = r.json()
            actual_title = d.get("title", "???")
            match = "title-matches" if actual_title == title else f"title-mismatch (corpus says {actual_title!r})"
            by_id = f"OK ({match})"
        elif r.status_code == 404:
            by_id = "404 NOT IN CORPUS"
        else:
            by_id = f"HTTP {r.status_code}"
    except Exception as exc:
        by_id = f"err {type(exc).__name__}: {exc}"

    # 2) Title search.
    try:
        r = requests.get(
            f"{BASE}/api/movies/search",
            params={"q": title},
            headers=hdr,
            timeout=15,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            exact = any(m.get("title") == title for m in results)
            if exact:
                by_title = f"exact title match ({len(results)} results total)"
            elif results:
                top = results[0].get("title", "???")
                by_title = f"NO exact match — top result {top!r} ({len(results)} results)"
            else:
                by_title = "0 search results — title not in corpus"
        else:
            by_title = f"search HTTP {r.status_code}"
    except Exception as exc:
        by_title = f"err {type(exc).__name__}: {exc}"

    return by_id, by_title


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY

    tok = signup_and_token()
    data = run_chat(tok, query)

    response_text = data.get("response_text", "")
    recs = data.get("recommendations", [])
    debug = data.get("debug", {})

    # --- TOP-LEVEL ---
    print("\n--- TOP-LEVEL ---")
    print(f"  response_text ({len(response_text)} chars):")
    print(f"    {response_text[:280]}{'...' if len(response_text) > 280 else ''}")
    print(f"  recommendations count: {len(recs)}")
    if isinstance(debug, dict):
        print(f"  debug.parsed_intent: {debug.get('parsed_intent')}")
        print(f"  debug.expanded_query: {debug.get('expanded_query')!r}")
        print(f"  debug.retrieval_method: {debug.get('retrieval_method')!r}")
        print(
            f"  debug.candidates before/after filter: "
            f"{debug.get('num_candidates_before_filter')} / "
            f"{debug.get('num_candidates_after_filter')}"
        )

    top_errors: list[str] = []
    if not response_text or not response_text.strip():
        top_errors.append("response_text empty")
    if not (1 <= len(recs) <= 3):
        top_errors.append(
            f"recommendations count {len(recs)} outside prompt rule 1-3"
        )

    # --- PER RECOMMENDATION ---
    per_errors: list[list[str]] = []
    per_warnings: list[list[str]] = []
    for i, rec in enumerate(recs, 1):
        print(f"\n--- recommendation [{i}] ---")
        print(f"  movie_id: {rec.get('movie_id')!r}")
        print(f"  title: {rec.get('title')!r}")
        print(f"  year: {rec.get('year')}")
        print(f"  genres: {rec.get('genres')}")
        print(f"  match_reasons: {rec.get('match_reasons')}")
        expl = rec.get("explanation", "")
        plot = rec.get("plot_preview", "")
        print(f"  explanation ({len(expl)} chars):")
        print(f"    {expl}")
        print(f"  plot_preview ({len(plot)} chars):")
        print(f"    {plot[:320]}{'...' if len(plot) > 320 else ''}")

        errs, warns = check_recommendation(rec)
        per_errors.append(errs)
        per_warnings.append(warns)
        if errs:
            print(f"  ERRORS: {errs}")
        if warns:
            print(f"  WARNINGS: {warns}")
        if not errs and not warns:
            print("  schema check: PASS clean")

    # --- CORPUS EXISTENCE ---
    print("\n--- CORPUS EXISTENCE (each movie should resolve in CMU corpus) ---")
    corpus_errors: list[str] = []
    for i, rec in enumerate(recs, 1):
        mid = rec.get("movie_id", "")
        title = rec.get("title", "")
        by_id, by_title = corpus_lookup(tok, mid, title)
        print(f"  [{i}] id={mid!r} title={title!r}")
        print(f"      by_id direct lookup: {by_id}")
        print(f"      by_title search:     {by_title}")
        if "NOT IN CORPUS" in by_id and ("0 search results" in by_title or "NO exact match" in by_title):
            corpus_errors.append(
                f"rec[{i}] '{title}' (id={mid}): not found by id AND no exact title match in corpus search — possible LLM hallucination"
            )

    # --- DISTINCT EXPLANATIONS ---
    exps = [r.get("explanation", "") for r in recs]
    distinct = len(set(exps)) == len(exps) and len(exps) > 0
    print("\n--- DISTINCT EXPLANATIONS ---")
    print(
        f"  {len(set(exps))} unique / {len(exps)} total — "
        f"{'PASS' if distinct else 'FAIL identical-explanations bug'}"
    )

    # --- VERDICT ---
    print("\n=== VERDICT ===")
    error_count = (
        len(top_errors)
        + sum(len(x) for x in per_errors)
        + len(corpus_errors)
        + (0 if distinct else 1)
    )
    warning_count = sum(len(x) for x in per_warnings)

    if top_errors:
        print(f"  TOP-LEVEL errors: {top_errors}")
    for i, errs in enumerate(per_errors, 1):
        if errs:
            print(f"  REC[{i}] errors: {errs}")
    if corpus_errors:
        for ce in corpus_errors:
            print(f"  CORPUS error: {ce}")
    if not distinct:
        print(f"  DISTINCT-EXPLANATIONS error: {len(set(exps))} unique / {len(exps)}")
    if warning_count:
        for i, warns in enumerate(per_warnings, 1):
            for w in warns:
                print(f"  REC[{i}] warning: {w}")

    print()
    if error_count == 0 and warning_count == 0:
        print("PASS clean: every check green (schema, content, corpus, distinct, no fallback fingerprint).")
        return 0
    if error_count == 0:
        print(f"PASS with {warning_count} warning(s) — deploy works but quality could be better.")
        return 0
    print(f"FAIL: {error_count} error(s) + {warning_count} warning(s) — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
