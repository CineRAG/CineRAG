"""Chat orchestrator — single entry point for /api/chat.

This is the single entry point Person C's `/api/chat` endpoint calls.
See Contest/interface_contract.md §3 (process_chat pipeline).
"""
from __future__ import annotations

import logging
from typing import Any

from backend.rag.filter import filter_excluded, filter_watched
from backend.rag.generator import ResponseGenerator
from backend.rag.llm_client import OllamaClient
from backend.rag.query_expander import QueryExpander
from backend.rag.query_preprocessor import QueryPreprocessor
from backend.rag.reranker import rerank, crossencoder_rerank

logger = logging.getLogger(__name__)

def _rrf_fuse(ranked_lists: list[list[dict]], top_k: int, rrf_k: int = 60) -> list[dict]:
    rank_maps: list[dict[str, int]] = []
    meta_lookup: dict[str, dict] = {}
    for lst in ranked_lists:
        rank_maps.append({r["movie_id"]: i + 1 for i, r in enumerate(lst)})
        for r in lst:
            meta_lookup[r["movie_id"]] = r

    all_ids = set().union(*rank_maps)
    scores: dict[str, float] = {}
    for mid in all_ids:
        scores[mid] = sum(
            1.0 / (rrf_k + rm[mid]) for rm in rank_maps if mid in rm
        )

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
    result = []
    for mid in sorted_ids:
        entry = meta_lookup[mid].copy()
        entry["score"] = round(scores[mid], 6)
        result.append(entry)
    return result



SERVICE_UNAVAILABLE_TEXT = (
    "The recommendation service is temporarily unavailable. Please try again."
)


class ChatService:
    """Orchestrator for the /api/chat pipeline (Person B's single entry point)."""

    def __init__(self, retriever: Any, llm_client: OllamaClient) -> None:
        self.retriever = retriever
        self.llm_client = llm_client
        self.preprocessor = QueryPreprocessor(llm_client)
        self.expander = QueryExpander(llm_client)

        from sentence_transformers import CrossEncoder
        self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.generator = ResponseGenerator(llm_client)
        

    def process_chat(
        self,
        user_message: str,
        session_id: str,
        user_id: int,
        watched_movie_ids: set[str],
        conversation_history: list[dict] | None = None,
        exclude_movie_ids: set[str] | None = None,
    ) -> dict:
        debug: dict[str, Any] = {
            "parsed_intent": None,
            "expanded_query": "",
            "num_candidates_before_filter": 0,
            "num_candidates_after_filter": 0,
            "retrieval_method": "hybrid_rrf",
        }

        try:
            # 1. Parse intent
            parsed_intent = self.preprocessor.parse(user_message, conversation_history)

            # 2. Refinement stretch goal is OFF for Week 1 — treat as fresh query.
            if parsed_intent.get("intent") == "refine_previous":
                logger.info(
                    "ChatService: refine_previous detected, falling back to fresh query"
                )
                parsed_intent["intent"] = "find_by_mood"
                parsed_intent["refinement"] = None

            debug["parsed_intent"] = parsed_intent

            # 3. Short-circuit for general questions: skip stages 2-6.
            if parsed_intent.get("intent") == "general_question":
                debug["retrieval_method"] = "skipped"
                gen_result = self.generator.generate(
                    user_message=user_message,
                    reranked_movies=[],
                    parsed_intent=parsed_intent,
                    conversation_history=conversation_history,
                )
                return self._wrap(session_id, gen_result, debug)

            # 4. Reference resolution
            reference_movie_data = None
            title_hits: list[dict] = []
            if parsed_intent.get("reference_movie"):
                hits = self.retriever.search_by_title(
                    parsed_intent["reference_movie"], top_k=10
                )
                if hits:
                    reference_movie_data = hits[0]
                    title_hits = hits

            # 5. Expand
            expanded_query = self.expander.expand(parsed_intent, reference_movie_data)
            debug["expanded_query"] = expanded_query

            # 6. Retrieve
            raw_hits = self.retriever.retrieve_hybrid(user_message, top_k=50)
            exp_hits = self.retriever.retrieve_hybrid(expanded_query, top_k=50)
            lists_to_fuse = [raw_hits, exp_hits]
            if title_hits:
                lists_to_fuse.append(title_hits)
            candidates = _rrf_fuse(lists_to_fuse, top_k=50)



            debug["num_candidates_before_filter"] = len(candidates)

            # 7. Filter + rerank
            filtered = filter_watched(candidates, watched_movie_ids)
            if exclude_movie_ids:
                filtered = filter_excluded(filtered, exclude_movie_ids)
            debug["num_candidates_after_filter"] = len(filtered)

            filtered = crossencoder_rerank(user_message, filtered, self.cross_encoder, top_k=20)
            reranked = rerank(filtered, parsed_intent, top_k=5)

            # 8. Generate
            gen_result = self.generator.generate(
                user_message=user_message,
                reranked_movies=reranked,
                parsed_intent=parsed_intent,
                conversation_history=conversation_history,
            )
            return self._wrap(session_id, gen_result, debug)

        except (ConnectionError, TimeoutError, ImportError) as exc:
            logger.error(
                "ChatService: pipeline failed (%s): %s", type(exc).__name__, exc
            )
            return {
                "session_id": session_id,
                "response_text": SERVICE_UNAVAILABLE_TEXT,
                "recommendations": [],
                "debug": debug,
            }

    def _wrap(self, session_id: str, gen_result: dict, debug: dict) -> dict:
        return {
            "session_id": session_id,
            "response_text": gen_result["response_text"],
            "recommendations": gen_result["recommendations"],
            "debug": debug,
        }
