"""Stage 6 — grounded recommendation generation.

See Contest/interface_contract.md §3 for signature.
"""
from __future__ import annotations

import logging

from backend.rag._prompt_loader import load_prompt
from backend.rag.llm_client import OllamaClient

logger = logging.getLogger(__name__)

PLOT_PREVIEW_LEN = 300

EMPTY_FALLBACK_TEXT = (
    "I couldn't find good matches for that - could you try rephrasing or adding more detail?"
)
LLM_ERROR_FALLBACK_TEXT = (
    "I had some trouble putting together solid picks this time - could you try rephrasing?"
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


def _build_recommendation(pick: dict, source_movie: dict) -> dict:
    plot = source_movie.get("plot_summary", "")
    return {
        "movie_id": source_movie["movie_id"],
        "title": source_movie["title"],
        "year": source_movie.get("year"),
        "genres": list(source_movie.get("genres", [])),
        "explanation": pick.get("explanation", ""),
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
        prompt = template.format(
            user_message=user_message,
            intent=parsed_intent.get("intent", "find_by_mood"),
            conversation_history=_render_history(conversation_history),
            candidates_block=_render_candidates(reranked_movies),
        )
        result = self.llm_client.generate_json(prompt)

        if "error" in result:
            logger.warning("ResponseGenerator: LLM JSON failed, returning fallback")
            return {"response_text": LLM_ERROR_FALLBACK_TEXT, "recommendations": []}

        by_id = {m["movie_id"]: m for m in reranked_movies}
        recommendations = []
        for pick in result.get("picks", []):
            mid = pick.get("movie_id")
            source = by_id.get(mid)
            if not source:
                logger.warning("ResponseGenerator: pick references unknown movie_id %r", mid)
                continue
            recommendations.append(_build_recommendation(pick, source))

        return {
            "response_text": result.get("response_text", "").strip(),
            "recommendations": recommendations,
        }
