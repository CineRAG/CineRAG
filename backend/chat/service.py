"""Chat orchestrator — single entry point for /api/chat.

This is the single entry point Person C's `/api/chat` endpoint calls.
See Contest/interface_contract.md §3 (process_chat pipeline).
"""
from __future__ import annotations

import logging
from typing import Any

from backend.rag.generator import ResponseGenerator
from backend.rag.llm_client import OllamaClient
from backend.rag.query_expander import QueryExpander
from backend.rag.query_preprocessor import QueryPreprocessor

logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_TEXT = (
    "The recommendation service is temporarily unavailable. Please try again."
)


# TODO(week2): replace with backend.rag.filter.filter_watched (Person A)
def _filter_watched(candidates: list[dict], watched_ids: set[str]) -> list[dict]:
    """Local stand-in for Person A's filter — drops watched movies from candidates."""
    return [c for c in candidates if c["movie_id"] not in watched_ids]


# TODO(week2): replace with backend.rag.reranker.rerank (Person A)
def _rerank(candidates: list[dict], parsed_intent: dict, top_k: int = 5) -> list[dict]:
    """Local stand-in for Person A's reranker — passes through top_k by score."""
    del parsed_intent  # placeholder ignores intent; real reranker uses it
    return list(candidates[:top_k])


class ChatService:
    """Orchestrator for the /api/chat pipeline (Person B's single entry point)."""

    def __init__(self, retriever: Any, llm_client: OllamaClient) -> None:
        self.retriever = retriever
        self.llm_client = llm_client
        self.preprocessor = QueryPreprocessor(llm_client)
        self.expander = QueryExpander(llm_client)
        self.generator = ResponseGenerator(llm_client)

    def process_chat(
        self,
        user_message: str,
        session_id: str,
        user_id: int,
        watched_movie_ids: set[str],
        conversation_history: list[dict] | None = None,
    ) -> dict:
        debug: dict[str, Any] = {
            "parsed_intent": None,
            "expanded_query": "",
            "num_candidates_before_filter": 0,
            "num_candidates_after_filter": 0,
            "retrieval_method": "hybrid_rrf",
        }

        parsed_intent = self.preprocessor.parse(user_message, conversation_history)
        debug["parsed_intent"] = parsed_intent

        reference_movie_data = None
        if parsed_intent.get("reference_movie"):
            hits = self.retriever.search_by_title(parsed_intent["reference_movie"], top_k=1)
            if hits:
                reference_movie_data = hits[0]

        expanded_query = self.expander.expand(parsed_intent, reference_movie_data)
        debug["expanded_query"] = expanded_query

        candidates = self.retriever.retrieve_hybrid(expanded_query, top_k=50)
        debug["num_candidates_before_filter"] = len(candidates)

        filtered = _filter_watched(candidates, watched_movie_ids)
        debug["num_candidates_after_filter"] = len(filtered)

        reranked = _rerank(filtered, parsed_intent, top_k=5)

        gen_result = self.generator.generate(
            user_message=user_message,
            reranked_movies=reranked,
            parsed_intent=parsed_intent,
            conversation_history=conversation_history,
        )

        return {
            "session_id": session_id,
            "response_text": gen_result["response_text"],
            "recommendations": gen_result["recommendations"],
            "debug": debug,
        }
