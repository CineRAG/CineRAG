"""Unit tests for ResponseGenerator (Stage 6)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.rag.generator import ResponseGenerator
from backend.tests.llm.mock_data import MOCK_RETRIEVAL_RESULTS


PARSED_INTENT_RECOMMEND = {
    "intent": "find_by_mood",
    "reference_movie": None,
    "attributes": {"genre": "drama", "mood": "thoughtful", "era": None, "exclusions": None},
    "refinement": None,
}

PARSED_INTENT_GENERAL = {
    "intent": "general_question",
    "reference_movie": None,
    "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
    "refinement": None,
}


def _client_json(payload):
    c = MagicMock()
    c.generate_json.return_value = payload
    c.generate.return_value = "ok"
    return c


def _good_picks_payload():
    return {
        "response_text": "Here are some thoughtful picks.",
        "picks": [
            {
                "movie_id": "345678",
                "explanation": "Memory and love are central themes.",
                "match_reasons": ["shared theme: memory", "emotional core"],
            },
            {
                "movie_id": "567890",
                "explanation": "A meditation on time and choice.",
                "match_reasons": ["meditative pacing"],
            },
        ],
    }


class TestGenerate:
    def test_returns_response_text_and_recommendations(self):
        client = _client_json(_good_picks_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="something thoughtful",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["response_text"] == "Here are some thoughtful picks."
        assert len(out["recommendations"]) == 2
        rec = out["recommendations"][0]
        assert rec["movie_id"] == "345678"
        assert rec["title"] == "Eternal Sunshine of the Spotless Mind"
        assert rec["year"] == 2004
        assert rec["explanation"] == "Memory and love are central themes."
        assert rec["match_reasons"] == ["shared theme: memory", "emotional core"]

    def test_plot_preview_is_python_sliced_300_chars(self):
        client = _client_json(_good_picks_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        movie = next(m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == "345678")
        assert out["recommendations"][0]["plot_preview"] == movie["plot_summary"][:300]

    def test_empty_candidates_returns_apology_no_llm_call(self):
        client = _client_json({"response_text": "should not be called", "picks": []})
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=[],
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"] == []
        assert "couldn't find" in out["response_text"].lower() or "no" in out["response_text"].lower()
        client.generate_json.assert_not_called()
        client.generate.assert_not_called()

    def test_general_question_uses_plain_text_no_recs(self):
        client = MagicMock()
        client.generate.return_value = "Film noir is a 1940s style; neo-noir is its modern descendant."
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="What's neo-noir?",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_GENERAL,
        )
        assert out["recommendations"] == []
        assert "noir" in out["response_text"].lower()
        client.generate_json.assert_not_called()

    def test_llm_error_dict_returns_fallback(self):
        client = _client_json({"error": "json_parse_failed", "raw_response": "junk"})
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"] == []
        assert "rephrasing" in out["response_text"].lower() or "trouble" in out["response_text"].lower()

    def test_skips_picks_referencing_unknown_movie_ids(self):
        bad_payload = {
            "response_text": "Mixed picks.",
            "picks": [
                {"movie_id": "999999", "explanation": "fake", "match_reasons": []},
                {"movie_id": "456789", "explanation": "real", "match_reasons": ["dream logic"]},
            ],
        }
        client = _client_json(bad_payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert len(out["recommendations"]) == 1
        assert out["recommendations"][0]["movie_id"] == "456789"
