"""
backend/rag/reranker.py
Stage 5: Attribute-based score boosting from parsed intent.

Boosting rules (additive, applied to top-20 candidates):
  - genre match  : +0.20
  - era match    : +0.15
  - exclusion    : candidate removed entirely
  - mood         : no boost (handled upstream by semantic retrieval)

Final score = original_score * (1 + total_boost)
"""

from __future__ import annotations

import re


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_era_range(era_str: str) -> tuple[int, int] | None:
    """
    Convert era string → inclusive (start_year, end_year).
    Supports: "1990s", "90s", "2000s", "00s", "2010s", "10s" …
    Returns None if unrecognizable.
    """
    s = era_str.strip().lower()

    m = re.search(r"(\d{4})s", s)
    if m:
        start = int(m.group(1))
        return (start, start + 9)

    m = re.search(r"(\d{2})s", s)
    if m:
        two = int(m.group(1))
        century = 1900 if two >= 30 else 2000
        start = century + two
        return (start, start + 9)

    return None


def _genres_lower(movie: dict) -> list[str]:
    return [g.lower() for g in movie.get("genres", [])]


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def rerank(
    candidates: list[dict],
    parsed_intent: dict,
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank candidates based on attribute boosting from parsed_intent.

    Boosting rules:
      - If parsed_intent["attributes"]["genre"] is set, boost movies
        matching that genre by +0.20.
      - If parsed_intent["attributes"]["era"] is set (e.g. "1990s"),
        boost movies from that decade by +0.15.
      - If parsed_intent["attributes"]["exclusions"] is set (e.g. "no horror"),
        remove movies with that genre entirely.
      - If parsed_intent["attributes"]["mood"] is set, no boost applied
        (mood is handled by semantic retrieval upstream).

    Args:
        candidates:    list of MovieResult dicts (already filtered).
                       Only the first 20 are considered for efficiency.
        parsed_intent: ParsedIntent dict from Stage 1 (Person B).
        top_k:         number of results to return.

    Returns:
        top_k MovieResult dicts sorted by adjusted score descending.
    """
    pool       = candidates[:20]
    attributes = parsed_intent.get("attributes") or {}

    target_genre: str | None = (attributes.get("genre") or "").strip().lower() or None
    era_str: str | None      = (attributes.get("era") or "").strip() or None
    exclusions: str | None   = (attributes.get("exclusions") or "").strip().lower() or None

    # Normalise exclusion string — strip leading "no ", "not ", "without " …
    excl_genre: str | None = None
    if exclusions:
        excl_genre = re.sub(r"^(no|not|without|excludes?)\s+", "", exclusions).strip() or None

    era_range = _parse_era_range(era_str) if era_str else None

    reranked: list[dict] = []
    for movie in pool:
        genres = _genres_lower(movie)
        year: int | None = movie.get("year")

        # Exclusion filter
        if excl_genre and any(excl_genre in g for g in genres):
            continue

        # Boost calculation
        boost = 0.0
        if target_genre and any(target_genre in g for g in genres):
            boost += 0.20
        if era_range and year is not None:
            start, end = era_range
            if start <= year <= end:
                boost += 0.15

        adjusted = movie.get("score", 0.0) * (1.0 + boost)
        reranked.append({**movie, "score": round(adjusted, 6)})

    reranked.sort(key=lambda m: m["score"], reverse=True)
    return reranked[:top_k]

def crossencoder_rerank(
      query: str,
      candidates: list[dict],
      cross_encoder,
      top_k: int = 20,
  ) -> list[dict]:
      if not candidates:
          return candidates
      pairs = [(query, m.get("plot_summary", "")) for m in candidates]
      scores = cross_encoder.predict(pairs)
      for m, score in zip(candidates, scores):
          m = m.copy()
          m["score"] = float(score)
      candidates = [dict(m, score=float(s)) for m, s in zip(candidates, scores)]
      candidates.sort(key=lambda m: m["score"], reverse=True)
      return candidates[:top_k]