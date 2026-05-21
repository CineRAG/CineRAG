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

# Heuristic: 2+ capitalized words in a row, optionally joined by hyphen/apostrophe.
# Catches person names ("Christopher Nolan"), award/studio names ("Academy Award",
# "Warner Bros"), and similar leakage from the LLM's prior knowledge that may not
# appear in the candidate's plot summary.
_PROPER_NOUN_PATTERN = re.compile(
    r"\b[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)+\b"
)

# Phrases that signal external knowledge (credits, adaptation sources, awards,
# commercial framing). These never belong in grounded card explanations — even
# the lowercase form "directed by nolan" is a hallucination because the plot
# never lists crew. Catching the phrase covers single-name leakage that the
# multi-word proper-noun regex above misses ("directed by Nolan", "starring
# DiCaprio"). Matched case-insensitively with word boundaries.
_EXTERNAL_ATTRIBUTION_PHRASES = (
    # Crew / cast attribution
    "directed by",
    "from the director of",
    "from the directors of",
    "starring",
    "screenplay by",
    "written by",
    "produced by",
    "music by",
    "score by",
    "scored by",
    "composed by",
    "cinematography by",
    "shot by",
    "edited by",
    "from the makers of",
    "from the studio behind",
    # Adaptation source
    "based on the novel by",
    "based on the book by",
    "based on the play by",
    "based on the comic by",
    "adapted from the novel",
    "adapted from the book",
    # Awards & critical reception
    "academy award",
    "oscar-winning",
    "oscar-nominated",
    "oscar winner",
    "oscar nominee",
    "won an oscar",
    "won the oscar",
    "golden globe",
    "bafta",
    "palme d'or",
    # Commercial / franchise framing
    "box office",
    "blockbuster",
    "critically acclaimed",
    "critical acclaim",
    "best-selling",
    "bestselling",
)
_EXTERNAL_ATTRIBUTION_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(p) for p in _EXTERNAL_ATTRIBUTION_PHRASES)
    + r")\b",
    re.IGNORECASE,
)

# 4-digit years 1900-2099 — typical release/setting range for our catalog.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

EMPTY_FALLBACK_TEXT = (
    "I couldn't find good matches for that - could you try rephrasing or adding more detail?"
)
DETERMINISTIC_FALLBACK_TEXT = (
    "I found a few candidates from the movie corpus that best match your request. "
    "The explanations below are drawn from the retrieved plot summaries."
)
SAFE_INTRO_TEXT = (
    "I found some films from the catalog that match your request."
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


def _ungrounded_proper_nouns(text: str, plot: str, title: str) -> set[str]:
    """Return proper-noun phrases present in `text` but absent from `plot` and `title`.

    Used to detect hallucinated names (directors, actors, awards, studios) leaking
    into LLM explanations from the model's prior knowledge.
    """
    candidates = set(_PROPER_NOUN_PATTERN.findall(text))
    if not candidates:
        return set()
    haystack = (plot + " " + title).lower()
    return {n for n in candidates if n.lower() not in haystack}


def _external_attribution_phrase(text: str) -> str | None:
    """Return the first credit/award/franchise phrase found in `text`, or None.

    Credit phrases ("directed by", "starring", "based on the novel by") are
    structural signals of external knowledge regardless of whether the name that
    follows is multi-word capitalized. Catching the phrase covers single-name
    leaks the proper-noun regex misses.
    """
    m = _EXTERNAL_ATTRIBUTION_RE.search(text)
    return m.group(0) if m else None


def _ungrounded_years(text: str, plot: str, title: str, year: int | None) -> set[str]:
    """Return 4-digit years in `text` that aren't in plot/title and don't match `year`.

    Catches "this 1995 thriller" when the movie is actually 2010. A year is
    considered grounded if it appears literally in the plot or title, or if it
    equals the movie's catalog release year.
    """
    years = set(_YEAR_RE.findall(text))
    if not years:
        return set()
    haystack = (plot + " " + title).lower()
    source_year_str = str(year) if year is not None else None
    return {y for y in years if y not in haystack and y != source_year_str}


def _safe_plot_fallback(plot: str) -> str:
    """Trim `plot` to FALLBACK_EXPLANATION_LEN at a sentence boundary when possible."""
    snippet = plot[:FALLBACK_EXPLANATION_LEN].rstrip()
    last_period = snippet.rfind(".")
    if last_period > 40:
        return snippet[: last_period + 1]
    if len(plot) > FALLBACK_EXPLANATION_LEN:
        return snippet + "..."
    return snippet


def _ground_explanation(raw: str, plot: str, title: str, year: int | None = None) -> str:
    """Return `raw` if grounded; otherwise a plot-derived fallback.

    Sanitization fires on ANY of: ungrounded proper nouns, external-attribution
    phrases ("directed by", "Oscar-winning", ...), or 4-digit years that don't
    match the movie's plot/title/release year. Each trigger is logged separately
    so the team can see what the LLM is leaking. The plot snippet is grounded by
    construction (it comes from the candidate's own plot summary).
    """
    ungrounded_names = _ungrounded_proper_nouns(raw, plot, title)
    attribution = _external_attribution_phrase(raw)
    ungrounded_years = _ungrounded_years(raw, plot, title, year)
    if not ungrounded_names and not attribution and not ungrounded_years:
        return raw
    reasons: list[str] = []
    if ungrounded_names:
        reasons.append(f"ungrounded names {sorted(ungrounded_names)}")
    if attribution:
        reasons.append(f"attribution phrase {attribution!r}")
    if ungrounded_years:
        reasons.append(f"ungrounded years {sorted(ungrounded_years)}")
    logger.warning(
        "ResponseGenerator: explanation for %r is ungrounded (%s); replacing with plot-derived fallback",
        title, "; ".join(reasons),
    )
    return _safe_plot_fallback(plot)


def _ground_match_reasons(
    raw: list, plot: str, title: str, year: int | None = None
) -> list[str]:
    """Drop any match_reason tag that fails grounding checks."""
    kept: list[str] = []
    for r in raw:
        if not isinstance(r, str):
            continue
        if _ungrounded_proper_nouns(r, plot, title):
            logger.warning(
                "ResponseGenerator: dropped match_reason %r for %r (ungrounded names)",
                r, title,
            )
            continue
        attribution = _external_attribution_phrase(r)
        if attribution:
            logger.warning(
                "ResponseGenerator: dropped match_reason %r for %r (attribution phrase %r)",
                r, title, attribution,
            )
            continue
        if _ungrounded_years(r, plot, title, year):
            logger.warning(
                "ResponseGenerator: dropped match_reason %r for %r (ungrounded year)",
                r, title,
            )
            continue
        kept.append(r)
    return kept


def _ground_response_text(raw: str, candidate_titles: list[str]) -> str:
    """Return `raw` if grounded; otherwise a neutral safe intro.

    response_text spans all picks, so we can't plot-ground it. We instead block
    external-attribution phrases and multi-word proper nouns that aren't any
    candidate title. Candidate titles ARE allowed — the LLM may legitimately
    write "I've selected Inception for you."
    """
    if not raw:
        return raw
    attribution = _external_attribution_phrase(raw)
    titles_haystack = " ".join(candidate_titles).lower()
    multi_word_names = set(_PROPER_NOUN_PATTERN.findall(raw))
    ungrounded_names = {n for n in multi_word_names if n.lower() not in titles_haystack}
    if not attribution and not ungrounded_names:
        return raw
    reasons: list[str] = []
    if attribution:
        reasons.append(f"attribution phrase {attribution!r}")
    if ungrounded_names:
        reasons.append(f"ungrounded names {sorted(ungrounded_names)}")
    logger.warning(
        "ResponseGenerator: response_text is ungrounded (%s); replacing with safe default",
        "; ".join(reasons),
    )
    return SAFE_INTRO_TEXT


def _build_recommendation(pick: dict, source_movie: dict) -> dict:
    plot = source_movie.get("plot_summary", "")
    title = source_movie["title"]
    year = source_movie.get("year")
    explanation = _ground_explanation(pick.get("explanation", ""), plot, title, year)
    match_reasons = _ground_match_reasons(
        list(pick.get("match_reasons", [])), plot, title, year
    )
    if not match_reasons:
        # Never leave a card with zero tags; "retrieved match" is a neutral safe label.
        match_reasons = ["retrieved match"]
    return {
        "movie_id": source_movie["movie_id"],
        "title": title,
        "year": year,
        "genres": list(source_movie.get("genres", [])),
        "explanation": explanation,
        "plot_preview": plot[:PLOT_PREVIEW_LEN],
        "match_reasons": match_reasons,
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

        candidate_titles = [m["title"] for m in reranked_movies]

        first_result = self.llm_client.generate_json(base_prompt)
        first_picks_recs = self._validate_picks(first_result, reranked_movies)
        if first_picks_recs:
            return {
                "response_text": _ground_response_text(
                    first_result.get("response_text", "").strip(),
                    candidate_titles,
                ),
                "recommendations": first_picks_recs,
            }

        # First attempt produced zero valid picks (all-invalid IDs OR malformed JSON).
        # Retry once with the allowed IDs spelled out explicitly.
        logger.warning(
            "ResponseGenerator: first attempt returned 0 valid picks; retrying with explicit ID list"
        )
        retry_prompt = self._build_retry_prompt(base_prompt, reranked_movies)
        retry_result = self.llm_client.generate_json(retry_prompt)
        retry_recs = self._validate_picks(retry_result, reranked_movies)
        if retry_recs:
            return {
                "response_text": _ground_response_text(
                    retry_result.get("response_text", "").strip(),
                    candidate_titles,
                ),
                "recommendations": retry_recs,
            }

        logger.warning(
            "ResponseGenerator: retry also returned 0 valid picks; using deterministic top-%d fallback",
            FALLBACK_TOP_K,
        )
        return self._deterministic_fallback(reranked_movies, parsed_intent)

    def _validate_picks(self, result: dict, reranked_movies: list[dict]) -> list[dict]:
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
            recs.append(_build_recommendation(pick, source))
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
        for m in top:
            plot = m.get("plot_summary", "")
            explanation = plot[:FALLBACK_EXPLANATION_LEN].rstrip()
            if len(plot) > FALLBACK_EXPLANATION_LEN:
                explanation += "..."
            match_reasons = _fallback_match_reasons(m, attrs)
            recs.append(
                {
                    "movie_id": m["movie_id"],
                    "title": m["title"],
                    "year": m.get("year"),
                    "genres": list(m.get("genres", [])),
                    "explanation": explanation,
                    "plot_preview": plot[:PLOT_PREVIEW_LEN],
                    "match_reasons": match_reasons,
                }
            )
        return {
            "response_text": DETERMINISTIC_FALLBACK_TEXT,
            "recommendations": recs,
        }
