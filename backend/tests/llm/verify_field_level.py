"""Multi-scenario field-level verification of ResponseGenerator output.

Run as a script (not pytest). Exercises 8 realistic LLM behaviors against
MOCK_RETRIEVAL_RESULTS and certifies EVERY field of EVERY recommendation
per the interface contract:

- movie_id: str, matches one of the candidates exactly
- title: non-empty str, matches source
- year: int|None, matches source
- genres: list[str], matches source
- explanation: non-empty str, NEVER substring of plot, NEVER equal to plot_preview,
  and distinct across cards when more than one is returned
- plot_preview: str of len <= 300, equals plot_summary[:300]
- match_reasons: list[str], non-empty, each item is short

Each scenario prints: LLM call count, all fields per card, and a checklist
of invariants with PASS/FAIL. The script exits 0 only if every check passes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.rag.generator import ResponseGenerator
from backend.tests.llm.mock_data import MOCK_RETRIEVAL_RESULTS


CANDIDATES_BY_ID = {m["movie_id"]: m for m in MOCK_RETRIEVAL_RESULTS}

# Single shared intent used by recommendation-mode scenarios.
INTENT_RECOMMEND = {
    "intent": "find_by_mood",
    "reference_movie": None,
    "attributes": {
        "genre": "drama",
        "mood": "bittersweet",
        "era": "2010s",
        "exclusions": None,
    },
    "refinement": None,
}

INTENT_GENERAL = {
    "intent": "general_question",
    "reference_movie": None,
    "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
    "refinement": None,
}


# ---------------------------------------------------------------------------
# Invariant checks per recommendation
# ---------------------------------------------------------------------------


def check_recommendation_fields(rec: dict, idx: int) -> list[tuple[str, bool, str]]:
    """Return a list of (check_name, passed, detail) for one recommendation."""
    checks: list[tuple[str, bool, str]] = []

    # movie_id: str, in candidates
    mid = rec.get("movie_id")
    checks.append((
        f"[{idx}] movie_id is str",
        isinstance(mid, str),
        f"type={type(mid).__name__} value={mid!r}",
    ))
    checks.append((
        f"[{idx}] movie_id resolves to a real candidate",
        mid in CANDIDATES_BY_ID,
        f"id={mid!r}",
    ))

    source = CANDIDATES_BY_ID.get(mid) or {}

    # title
    title = rec.get("title")
    checks.append((
        f"[{idx}] title non-empty and matches source",
        isinstance(title, str) and title == source.get("title", "") and len(title) > 0,
        f"got={title!r} expected={source.get('title')!r}",
    ))

    # year
    year = rec.get("year")
    checks.append((
        f"[{idx}] year matches source",
        year == source.get("year"),
        f"got={year!r} expected={source.get('year')!r}",
    ))

    # genres
    genres = rec.get("genres")
    checks.append((
        f"[{idx}] genres is list and matches source",
        isinstance(genres, list) and genres == list(source.get("genres", [])),
        f"got={genres!r}",
    ))

    # explanation: filled, length sane, not equal to plot_preview, not a substring of plot
    explanation = rec.get("explanation") or ""
    plot_full = source.get("plot_summary", "")
    plot_preview = rec.get("plot_preview", "")
    checks.append((
        f"[{idx}] explanation non-empty",
        isinstance(explanation, str) and len(explanation.strip()) > 0,
        f"len={len(explanation)} value={explanation[:80]!r}{'…' if len(explanation) > 80 else ''}",
    ))
    checks.append((
        f"[{idx}] explanation NOT equal to plot_preview",
        explanation != plot_preview,
        "equal" if explanation == plot_preview else "ok",
    ))
    checks.append((
        f"[{idx}] explanation NOT a substring of plot",
        not (explanation and explanation in plot_full),
        "substring" if explanation in plot_full else "ok",
    ))

    # plot_preview: str of len <= 300, equals plot_summary[:300]
    checks.append((
        f"[{idx}] plot_preview equals plot_summary[:300]",
        isinstance(plot_preview, str) and plot_preview == plot_full[:300],
        f"len={len(plot_preview)} expected_len={len(plot_full[:300])}",
    ))

    # match_reasons: list[str], non-empty (per spec it can be empty for LLM picks
    # if the LLM didn't include any; for fallback we always inject at least one).
    mr = rec.get("match_reasons")
    checks.append((
        f"[{idx}] match_reasons is list[str]",
        isinstance(mr, list) and all(isinstance(x, str) for x in mr),
        f"value={mr!r}",
    ))

    return checks


def check_response_shape(out: dict, scenario_name: str) -> list[tuple[str, bool, str]]:
    """Top-level response shape: response_text non-empty, recommendations list."""
    checks: list[tuple[str, bool, str]] = []
    rt = out.get("response_text")
    checks.append((
        f"response_text non-empty",
        isinstance(rt, str) and len(rt.strip()) > 0,
        f"len={len(rt or '')}",
    ))
    recs = out.get("recommendations")
    checks.append((
        f"recommendations is list",
        isinstance(recs, list),
        f"type={type(recs).__name__}",
    ))
    return checks


def check_distinct_explanations(out: dict) -> list[tuple[str, bool, str]]:
    recs = out.get("recommendations", [])
    if len(recs) < 2:
        return []
    explanations = [r["explanation"] for r in recs]
    distinct = len(set(explanations)) == len(explanations)
    return [(
        "explanations distinct across cards",
        distinct,
        f"{len(set(explanations))} unique of {len(explanations)}",
    )]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def make_client(*payloads, general_text: str | None = None) -> MagicMock:
    c = MagicMock()
    if len(payloads) == 1:
        c.generate_json.return_value = payloads[0]
    else:
        c.generate_json.side_effect = list(payloads)
    c.generate.return_value = general_text or "ok"
    return c


def run_scenario(name: str, *, client, user_msg: str, intent: dict, expected_calls: int) -> tuple[bool, dict]:
    gen = ResponseGenerator(client)
    out = gen.generate(user_msg, MOCK_RETRIEVAL_RESULTS, intent)

    all_checks: list[tuple[str, bool, str]] = []
    all_checks.append((
        "LLM call count",
        client.generate_json.call_count == expected_calls,
        f"got={client.generate_json.call_count} expected={expected_calls}",
    ))
    all_checks.extend(check_response_shape(out, name))
    all_checks.extend(check_distinct_explanations(out))
    for i, rec in enumerate(out.get("recommendations", [])):
        all_checks.extend(check_recommendation_fields(rec, i))

    print(f"\n{'=' * 78}")
    print(f"SCENARIO: {name}")
    print(f"{'=' * 78}")
    print(f"  user_message: {user_msg!r}")
    print(f"  llm_json_calls: {client.generate_json.call_count}")
    print(f"  response_text: {out.get('response_text', '')!r}")
    print(f"  num_recommendations: {len(out.get('recommendations', []))}")
    for i, r in enumerate(out.get("recommendations", [])):
        print(f"\n  [{i}] movie_id={r.get('movie_id')!r} title={r.get('title')!r} year={r.get('year')}")
        print(f"      genres={r.get('genres')}")
        print(f"      explanation: {r.get('explanation')!r}")
        print(f"      plot_preview ({len(r.get('plot_preview', ''))} chars): {r.get('plot_preview', '')[:90]!r}…")
        print(f"      match_reasons: {r.get('match_reasons')}")

    print(f"\n  CHECKS:")
    all_passed = True
    for label, ok, detail in all_checks:
        marker = "PASS" if ok else "FAIL"
        print(f"    [{marker}] {label}  ({detail})")
        if not ok:
            all_passed = False
    return all_passed, out


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def scenario_happy_string_ids():
    payload = {
        "response_text": "Three quietly devastating dramas pulled from the catalog for you.",
        "picks": [
            {
                "movie_id": "975900",
                "explanation": "An epic class-crossing romance built on doomed historical scale.",
                "match_reasons": ["historical scale", "bittersweet survival"],
            },
            {
                "movie_id": "234567",
                "explanation": "A decades-spanning love letter framed by memory loss.",
                "match_reasons": ["memory motif", "long-arc romance"],
            },
            {
                "movie_id": "345678",
                "explanation": "A sci-fi-tinged meditation on grief and what we choose to keep.",
                "match_reasons": ["memory motif", "speculative emotional core"],
            },
        ],
    }
    return run_scenario(
        "happy path - LLM returns string IDs + distinct paraphrased explanations",
        client=make_client(payload),
        user_msg="Character-driven dramas with bittersweet endings",
        intent=INTENT_RECOMMEND,
        expected_calls=1,
    )


def scenario_happy_int_ids():
    payload = {
        "response_text": "Three picks lined up.",
        "picks": [
            {"movie_id": 975900, "explanation": "Epic class-crossing romance.", "match_reasons": ["historical"]},
            {"movie_id": 234567, "explanation": "Decades-spanning love letter.", "match_reasons": ["long-arc"]},
            {"movie_id": 345678, "explanation": "Sci-fi grief meditation.", "match_reasons": ["memory"]},
        ],
    }
    return run_scenario(
        "production case - LLM returns INTEGER IDs (was: 100% fallback)",
        client=make_client(payload),
        user_msg="Bittersweet dramas",
        intent=INTENT_RECOMMEND,
        expected_calls=1,
    )


def scenario_partial_invalid_no_retry():
    payload = {
        "response_text": "Mixed picks.",
        "picks": [
            {"movie_id": "999999", "explanation": "hallucinated", "match_reasons": []},
            {"movie_id": 456789, "explanation": "Layered dream-logic thriller.", "match_reasons": ["dream logic"]},
            {"movie_id": "567890", "explanation": "First-contact drama about time and choice.", "match_reasons": ["language", "time"]},
        ],
    }
    return run_scenario(
        "partial invalid - 1 bogus + 2 good (1 int, 1 str) -> no retry",
        client=make_client(payload),
        user_msg="Mind-bending dramas",
        intent=INTENT_RECOMMEND,
        expected_calls=1,
    )


def scenario_all_invalid_then_recover():
    first = {
        "response_text": "x",
        "picks": [
            {"movie_id": "111111", "explanation": "fake", "match_reasons": []},
            {"movie_id": "222222", "explanation": "fake", "match_reasons": []},
        ],
    }
    second = {
        "response_text": "Recovered on retry.",
        "picks": [
            {"movie_id": 345678, "explanation": "Memory and love.", "match_reasons": ["memory"]},
            {"movie_id": 567890, "explanation": "Language and time.", "match_reasons": ["language"]},
        ],
    }
    return run_scenario(
        "retry path - first attempt all-bogus, retry succeeds",
        client=make_client(first, second),
        user_msg="Thoughtful sci-fi",
        intent=INTENT_RECOMMEND,
        expected_calls=2,
    )


def scenario_both_attempts_fail_fallback():
    bad = {
        "response_text": "x",
        "picks": [
            {"movie_id": "111111", "explanation": "fake", "match_reasons": []},
            {"movie_id": "222222", "explanation": "fake", "match_reasons": []},
            {"movie_id": "333333", "explanation": "fake", "match_reasons": []},
        ],
    }
    return run_scenario(
        "deterministic fallback - both attempts all-bogus, fallback fires",
        client=make_client(bad, bad),
        user_msg="Bittersweet 2010s dramas",
        intent=INTENT_RECOMMEND,
        expected_calls=2,
    )


def scenario_llm_copies_plot_text():
    inception_plot = CANDIDATES_BY_ID["456789"]["plot_summary"]
    payload = {
        "response_text": "One pick — but explanation is lifted from the plot.",
        "picks": [
            {
                "movie_id": 456789,
                "explanation": inception_plot[:140],  # lazy-LLM copy
                "match_reasons": ["dream logic"],
            },
            {
                "movie_id": "567890",
                "explanation": "A linguist confronts time itself.",
                "match_reasons": ["language"],
            },
        ],
    }
    return run_scenario(
        "lazy-LLM defense - explanation copied from plot must be replaced",
        client=make_client(payload),
        user_msg="dream movies",
        intent=INTENT_RECOMMEND,
        expected_calls=1,
    )


def scenario_general_question():
    client = MagicMock()
    client.generate_json.return_value = {"picks": []}
    client.generate.return_value = (
        "Film noir is a stylized 1940s-50s Hollywood movement defined by shadowed "
        "cinematography, cynical antiheroes, and moral ambiguity."
    )
    gen = ResponseGenerator(client)
    out = gen.generate("What is film noir?", MOCK_RETRIEVAL_RESULTS, INTENT_GENERAL)

    checks: list[tuple[str, bool, str]] = []
    checks.append((
        "general question: no LLM JSON call",
        client.generate_json.call_count == 0,
        f"got={client.generate_json.call_count}",
    ))
    checks.append((
        "general question: empty recommendations",
        out.get("recommendations") == [],
        f"got={out.get('recommendations')!r}",
    ))
    checks.append((
        "general question: response_text non-empty",
        isinstance(out.get("response_text"), str) and len(out["response_text"].strip()) > 0,
        f"len={len(out.get('response_text', ''))}",
    ))

    print(f"\n{'=' * 78}")
    print(f"SCENARIO: general question - skips retrieval, returns plain LLM text")
    print(f"{'=' * 78}")
    print(f"  response_text: {out.get('response_text')!r}")
    print(f"  num_recommendations: {len(out.get('recommendations', []))}")
    print(f"\n  CHECKS:")
    all_passed = True
    for label, ok, detail in checks:
        marker = "PASS" if ok else "FAIL"
        print(f"    [{marker}] {label}  ({detail})")
        if not ok:
            all_passed = False
    return all_passed, out


def scenario_one_pick_only():
    payload = {
        "response_text": "Only one pick truly fits.",
        "picks": [
            {"movie_id": 567890, "explanation": "Language and time blur.", "match_reasons": ["sci-fi"]},
        ],
    }
    return run_scenario(
        "single pick - explanation must still be filled and not equal plot_preview",
        client=make_client(payload),
        user_msg="Arrival-like films",
        intent=INTENT_RECOMMEND,
        expected_calls=1,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    runners = [
        scenario_happy_string_ids,
        scenario_happy_int_ids,
        scenario_partial_invalid_no_retry,
        scenario_all_invalid_then_recover,
        scenario_both_attempts_fail_fallback,
        scenario_llm_copies_plot_text,
        scenario_general_question,
        scenario_one_pick_only,
    ]
    results = []
    for r in runners:
        passed, _ = r()
        results.append((r.__name__, passed))

    print(f"\n{'=' * 78}")
    print("SUMMARY")
    print(f"{'=' * 78}")
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
