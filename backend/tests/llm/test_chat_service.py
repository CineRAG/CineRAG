"""Unit tests for ChatService orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.chat.service import ChatService
from backend.tests.llm.mock_data import MOCK_RETRIEVAL_RESULTS


def _make_retriever():
    """Mock retriever that returns the 5 fixed movies for any query."""
    r = MagicMock()
    r.retrieve_hybrid.return_value = list(MOCK_RETRIEVAL_RESULTS)
    r.retrieve_by_movie_id.side_effect = lambda mid: next(
        (m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == mid), None
    )
    r.search_by_title.return_value = [MOCK_RETRIEVAL_RESULTS[3]]  # Inception
    return r


def _make_llm():
    return MagicMock()


def _stub_pipeline(service, parsed_intent, expanded_query, generator_result):
    service.preprocessor = MagicMock()
    service.preprocessor.parse.return_value = parsed_intent
    service.expander = MagicMock()
    service.expander.expand.return_value = expanded_query
    service.generator = MagicMock()
    service.generator.generate.return_value = generator_result


def test_full_pipeline_produces_chat_response_shape():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)

    parsed = {
        "intent": "find_by_mood",
        "reference_movie": None,
        "attributes": {"genre": "sci-fi", "mood": "thoughtful", "era": None, "exclusions": None},
        "refinement": None,
    }
    gen_result = {
        "response_text": "Here are some thoughtful picks.",
        "recommendations": [
            {
                "movie_id": "345678",
                "title": "Eternal Sunshine of the Spotless Mind",
                "year": 2004,
                "genres": ["Drama", "Romance", "Science Fiction"],
                "explanation": "Memory and identity.",
                "plot_preview": "...",
                "match_reasons": ["memory"],
            }
        ],
    }
    _stub_pipeline(service, parsed, "expanded query text", gen_result)

    out = service.process_chat(
        user_message="something thoughtful",
        session_id="s1",
        user_id=42,
        watched_movie_ids=set(),
    )

    assert out["session_id"] == "s1"
    assert out["response_text"] == "Here are some thoughtful picks."
    assert len(out["recommendations"]) == 1
    assert out["debug"]["parsed_intent"] == parsed
    assert out["debug"]["expanded_query"] == "expanded query text"
    assert out["debug"]["retrieval_method"] == "hybrid_rrf"
    assert out["debug"]["num_candidates_before_filter"] == 5
