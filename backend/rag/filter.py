"""
backend/rag/filter.py
Stage 4: Remove already-watched movies from the candidate list.
"""

from __future__ import annotations


def filter_watched(
    candidates: list[dict],
    watched_movie_ids: set[str],
) -> list[dict]:
    """
    Remove any candidate whose movie_id is in watched_movie_ids.
    Preserves original ordering.

    Args:
        candidates:        list of MovieResult dicts from retriever
        watched_movie_ids: set of movie_id strings the user has watched

    Returns:
        filtered list of MovieResult dicts
    """
    return filter_excluded(candidates, watched_movie_ids)


def filter_excluded(
    candidates: list[dict],
    excluded_movie_ids: set[str],
) -> list[dict]:
    """Remove candidates whose movie_id is in excluded_movie_ids."""
    if not excluded_movie_ids:
        return list(candidates)
    return [c for c in candidates if c["movie_id"] not in excluded_movie_ids]
