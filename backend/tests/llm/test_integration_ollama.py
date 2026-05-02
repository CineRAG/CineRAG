"""Integration tests against a live local Ollama.

This module self-skips when Ollama is not reachable, so the test suite stays
green on machines without Ollama installed. To run, ensure `ollama serve` is
running and `mistral` is pulled, then:

    pytest backend/tests/llm/test_integration_ollama.py -v
"""
from __future__ import annotations

import pytest
import requests

from backend.chat.service import ChatService
from backend.rag.llm_client import OllamaClient
from backend.rag.query_preprocessor import QueryPreprocessor
from backend.tests.llm.mock_data import MOCK_RETRIEVAL_RESULTS


def _ollama_reachable() -> bool:
    try:
        requests.get("http://localhost:11434/", timeout=2)
        return True
    except Exception:
        return False


if not _ollama_reachable():
    pytest.skip(
        "Ollama not running on http://localhost:11434 — start with `ollama serve` to run these tests",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def live_client() -> OllamaClient:
    return OllamaClient()


def test_generate_returns_non_empty_string(live_client):
    out = live_client.generate("Say hello in one word.", max_tokens=10)
    assert isinstance(out, str)
    assert len(out.strip()) > 0


def test_preprocessor_returns_well_formed_parsed_intent(live_client):
    preprocessor = QueryPreprocessor(live_client)
    out = preprocessor.parse("Movies like Inception but more emotional")
    assert out["intent"] in {"find_similar", "find_by_mood", "refine_previous", "general_question"}
    assert "attributes" in out
    assert {"genre", "mood", "era", "exclusions"}.issubset(out["attributes"].keys())


def test_chat_service_end_to_end_with_mock_retriever(live_client):
    from unittest.mock import MagicMock

    retriever = MagicMock()
    retriever.retrieve_hybrid.return_value = list(MOCK_RETRIEVAL_RESULTS)
    retriever.retrieve_by_movie_id.return_value = None
    retriever.search_by_title.return_value = [MOCK_RETRIEVAL_RESULTS[3]]

    service = ChatService(retriever=retriever, llm_client=live_client)
    out = service.process_chat(
        user_message="A thoughtful sci-fi movie about memory",
        session_id="integration-1",
        user_id=1,
        watched_movie_ids=set(),
    )

    assert isinstance(out["response_text"], str)
    assert len(out["response_text"].strip()) > 0
    assert isinstance(out["recommendations"], list)
    assert out["debug"]["parsed_intent"] is not None
    assert "retrieval_method" in out["debug"]
