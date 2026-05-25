"""Stage 6 — grounded recommendation generation.

See Contest/interface_contract.md §3 for signature.
"""
from __future__ import annotations

import logging
import re

from backend.rag._prompt_loader import load_prompt
from backend.rag.llm_client import OllamaClient

logger = logging.getLogger(__name__)

PLOT_PREVIEW_LEN = 300
FALLBACK_TOP_K = 3
FALLBACK_EXPLANATION_LEN = 220

EMPTY_FALLBACK_TEXT = (
    "I couldn't find good matches for that - could you try rephrasing or adding more detail?"
)
DETERMINISTIC_FALLBACK_TEXT = (
    "I found a few candidates from the movie corpus that best match your request. "
    "The explanations below are drawn from the retrieved plot summaries."
)

# Index-based intros so the N fallback cards never read as carbon copies of
# each other even when their metadata happens to overlap (same genre/year).
_FALLBACK_INTROS = (
    "A top match",
    "Another close fit",
    "Also surfaced",
)


def _render_history(history: list[dict] | None) -> str:
    if not history:
        return "(none)"
    lines = []
    for turn in history[-5:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


def _render_candidates(movies: list[dict]) -> str:
    lines = []
    for i, m in enumerate(movies, 1):
        genres = ", ".join(m.get("genres", []))
        year = m.get("year") or "?"
        lines.append(
            f"[{i}] movie_id={m['movie_id']} | {m['title']} ({year}) | "
            f"genres: {genres}\n    plot: {m.get('plot_summary', '')}"
        )
    return "\n\n".join(lines)


def _safe_per_movie_explanation(
    movie: dict, attrs: dict | None, index: int
) -> str:
    """Deterministic per-movie explanation that never quotes the plot.

    Used whenever the LLM cannot be trusted to write the explanation: both
    fallback paths (LLM picked invalid IDs, LLM copied plot text into the
    explanation). Builds the sentence from structured metadata only — year,
    primary genre, and any matched attributes from parsed_intent — so the
    output is visibly distinct from the plot_preview citation rendered below
    the card. The index-based intro guarantees the 3 fallback cards never
    look like duplicates even if their genre/year overlap.
    """
    intro = _FALLBACK_INTROS[index % len(_FALLBACK_INTROS)]
    genres = movie.get("genres") or []
    year = movie.get("year")
    descriptor_bits: list[str] = []
    if year:
        descriptor_bits.append(str(year))
    if genres:
        descriptor_bits.append(genres[0].lower())
    descriptor = " ".join(descriptor_bits) or "candidate"

    qualifier = "your query"
    if attrs:
        mood = (attrs.get("mood") or "").strip().lower()
        era = (attrs.get("era") or "").strip().lower()
        if mood:
            qualifier = f"your {mood} query"
        elif era:
            qualifier = f"your {era}-era query"

    return (
        f"{intro} from the catalog — a {descriptor} aligned with {qualifier}. "
        "See the plot summary below."
    )


def _fallback_match_reasons(movie: dict, attrs: dict) -> list[str]:
    reasons: list[str] = []
    genre = attrs.get("genre")
    if genre:
        reasons.append(f"genre: {genre}")
    mood = attrs.get("mood")
    if mood:
        reasons.append(f"mood: {mood}")
    era = attrs.get("era")
    if era:
        reasons.append(f"era: {era}")
    if not reasons:
        movie_genres = movie.get("genres") or []
        if movie_genres:
            reasons.append(f"genre: {movie_genres[0].lower()}")
        else:
            reasons.append("retrieved match")
    return reasons


_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize_for_similarity(s: str) -> str:
    """Lowercase, drop non-word/whitespace chars, collapse whitespace."""
    return " ".join(_PUNCT_RE.sub(" ", s.lower()).split())


def _explanation_duplicates_plot(
    explanation: str, plot: str, min_run: int = 60
) -> bool:
    """True when the LLM's explanation is effectively a slice of the plot.

    Catches the lazy-LLM mode where the model copies (or barely edits) a chunk
    of the plot summary into the explanation field. The card UI also renders
    plot_preview as a citation just below, so a copy makes the two read 95%
    identical. Heuristic: normalize both (lowercase, strip punctuation, collapse
    whitespace); if the normalized explanation as a whole — or any contiguous
    `min_run`-char window of it — appears inside the normalized plot, treat as
    duplication. `min_run = 60` is roughly one short clause; small enough to
    catch real copies, large enough to skip incidental phrase overlap.
    """
    if not explanation or not plot:
        return False
    norm_exp = _normalize_for_similarity(explanation)
    norm_plot = _normalize_for_similarity(plot)
    if len(norm_exp) < min_run:
        return norm_exp in norm_plot and len(norm_exp) >= 20
    if norm_exp in norm_plot:
        return True
    # Slide a window across the explanation; any contiguous run that lives in
    # the plot signals the LLM lifted text.
    step = max(1, min_run // 3)
    for i in range(0, len(norm_exp) - min_run + 1, step):
        if norm_exp[i:i + min_run] in norm_plot:
            return True
    return False


def _build_recommendation(
    pick: dict,
    source_movie: dict,
    index: int,
    attrs: dict | None,
) -> dict:
    plot = source_movie.get("plot_summary", "")
    raw_explanation = pick.get("explanation", "") or ""
    if _explanation_duplicates_plot(raw_explanation, plot):
        logger.warning(
            "ResponseGenerator: explanation for %r duplicates plot text; replacing with safe fallback",
            source_movie.get("title"),
        )
        explanation = _safe_per_movie_explanation(source_movie, attrs, index)
    else:
        explanation = raw_explanation
    return {
        "movie_id": source_movie["movie_id"],
        "title": source_movie["title"],
        "year": source_movie.get("year"),
        "genres": list(source_movie.get("genres", [])),
        "explanation": explanation,
        "plot_preview": plot[:PLOT_PREVIEW_LEN],
        "match_reasons": list(pick.get("match_reasons", [])),
    }


class ResponseGenerator:
    """Stage 6: generate grounded recommendations + intro text."""

    def __init__(self, llm_client: OllamaClient) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        user_message: str,
        reranked_movies: list[dict],
        parsed_intent: dict,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        if parsed_intent.get("intent") == "general_question":
            return self._generate_general_question(user_message, conversation_history)

        if not reranked_movies:
            logger.info("ResponseGenerator: empty candidates, returning apology")
            return {"response_text": EMPTY_FALLBACK_TEXT, "recommendations": []}

        return self._generate_recommendations(
            user_message=user_message,
            reranked_movies=reranked_movies,
            parsed_intent=parsed_intent,
            conversation_history=conversation_history,
        )

    def _generate_general_question(
        self,
        user_message: str,
        conversation_history: list[dict] | None,
    ) -> dict:
        template = load_prompt("generation_general")
        prompt = template.format(
            user_message=user_message,
            conversation_history=_render_history(conversation_history),
        )
        text = self.llm_client.generate(prompt, temperature=0.7).strip()
        return {"response_text": text, "recommendations": []}

    def _generate_recommendations(
        self,
        user_message: str,
        reranked_movies: list[dict],
        parsed_intent: dict,
        conversation_history: list[dict] | None,
    ) -> dict:
        template = load_prompt("generation_recommend")
        base_prompt = template.format(
            user_message=user_message,
            intent=parsed_intent.get("intent", "find_by_mood"),
            conversation_history=_render_history(conversation_history),
            candidates_block=_render_candidates(reranked_movies),
        )

        attrs = (parsed_intent.get("attributes") or {}) if parsed_intent else {}

        first_result = self.llm_client.generate_json(base_prompt)
        first_picks_recs = self._validate_picks(first_result, reranked_movies, attrs)
        if first_picks_recs:
            return {
                "response_text": first_result.get("response_text", "").strip(),
                "recommendations": first_picks_recs,
            }

        # First attempt produced zero valid picks (all-invalid IDs OR malformed JSON).
        # Retry once with the allowed IDs spelled out explicitly.
        logger.warning(
            "ResponseGenerator: first attempt returned 0 valid picks; retrying with explicit ID list"
        )
        retry_prompt = self._build_retry_prompt(base_prompt, reranked_movies)
        retry_result = self.llm_client.generate_json(retry_prompt)
        retry_recs = self._validate_picks(retry_result, reranked_movies, attrs)
        if retry_recs:
            return {
                "response_text": retry_result.get("response_text", "").strip(),
                "recommendations": retry_recs,
            }

        logger.warning(
            "ResponseGenerator: retry also returned 0 valid picks; using deterministic top-%d fallback",
            FALLBACK_TOP_K,
        )
        return self._deterministic_fallback(reranked_movies, parsed_intent)

    def _validate_picks(
        self,
        result: dict,
        reranked_movies: list[dict],
        attrs: dict | None = None,
    ) -> list[dict]:
        """Return Recommendation dicts for picks whose movie_id is in reranked_movies.

        Returns [] if `result` is an LLM error dict, picks is missing/empty, or every
        pick references an unknown movie_id. Hallucinated IDs are dropped silently
        with a warning log — they must never reach the frontend.
        """
        if "error" in result:
            return []
        by_id = {m["movie_id"]: m for m in reranked_movies}
        recs: list[dict] = []
        for pick in result.get("picks", []):
            mid = pick.get("movie_id")
            source = by_id.get(mid)
            if not source:
                logger.warning("ResponseGenerator: pick references unknown movie_id %r", mid)
                continue
            recs.append(_build_recommendation(pick, source, len(recs), attrs))
        return recs

    def _build_retry_prompt(self, base_prompt: str, reranked_movies: list[dict]) -> str:
        allowed_block = "\n".join(f"- {m['movie_id']}" for m in reranked_movies)
        addendum = (
            "\n\nRETRY NOTICE: your previous response used movie_id values that were not in "
            "the CANDIDATES list. Allowed movie_id values, exactly:\n"
            f"{allowed_block}\n"
            "Return JSON again. Every pick.movie_id MUST be one of those exact values, "
            "copied character-for-character. Do not invent IDs. Do not use titles as IDs."
        )
        return base_prompt + addendum

    def _deterministic_fallback(
        self, reranked_movies: list[dict], parsed_intent: dict
    ) -> dict:
        """Build Recommendation objects directly from the top reranked movies.

        Used when both LLM attempts fail to produce any valid pick. Guarantees that
        `recommendations` is non-empty whenever `reranked_movies` is non-empty, so
        the API never returns text claiming picks while `recommendations: []`.
        """
        top = reranked_movies[:FALLBACK_TOP_K]
        attrs = (parsed_intent.get("attributes") or {}) if parsed_intent else {}
        recs: list[dict] = []
        for index, m in enumerate(top):
            plot = m.get("plot_summary", "")
            match_reasons = _fallback_match_reasons(m, attrs)
            recs.append(
                {
                    "movie_id": m["movie_id"],
                    "title": m["title"],
                    "year": m.get("year"),
                    "genres": list(m.get("genres", [])),
                    "explanation": _safe_per_movie_explanation(m, attrs, index),
                    "plot_preview": plot[:PLOT_PREVIEW_LEN],
                    "match_reasons": match_reasons,
                }
            )
        return {
            "response_text": DETERMINISTIC_FALLBACK_TEXT,
            "recommendations": recs,
        }
