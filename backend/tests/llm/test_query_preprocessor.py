"""Unit tests for QueryPreprocessor (Stage 1)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.rag.query_preprocessor import QueryPreprocessor


SAFE_DEFAULT = {
    "intent": "find_by_mood",
    "reference_movie": None,
    "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
    "refinement": None,
}


def _make_client(json_return):
    client = MagicMock()
    client.generate_json.return_value = json_return
    return client


class TestParse:
    def test_returns_parsed_intent_for_valid_llm_json(self):
        good = {
            "intent": "find_similar",
            "reference_movie": "Inception",
            "attributes": {"genre": None, "mood": "emotional", "era": None, "exclusions": None},
            "refinement": None,
        }
        client = _make_client(good)
        preprocessor = QueryPreprocessor(client)
        out = preprocessor.parse("Movies like Inception but more emotional")
        assert out == good

    def test_returns_safe_default_on_parser_error_dict(self):
        client = _make_client({"error": "json_parse_failed", "raw_response": "blah"})
        preprocessor = QueryPreprocessor(client)
        out = preprocessor.parse("anything")
        assert out == SAFE_DEFAULT

    def test_returns_safe_default_when_required_keys_missing(self):
        client = _make_client({"intent": "find_similar"})
        preprocessor = QueryPreprocessor(client)
        out = preprocessor.parse("anything")
        assert out == SAFE_DEFAULT

    def test_coerces_invalid_intent_to_find_by_mood(self):
        client = _make_client({
            "intent": "made_up_intent",
            "reference_movie": None,
            "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
            "refinement": None,
        })
        preprocessor = QueryPreprocessor(client)
        out = preprocessor.parse("anything")
        assert out["intent"] == "find_by_mood"

    def test_renders_empty_history_when_none(self):
        client = _make_client(SAFE_DEFAULT)
        preprocessor = QueryPreprocessor(client)
        preprocessor.parse("hi")
        prompt_sent = client.generate_json.call_args.args[0]
        assert "USER MESSAGE:\nhi" in prompt_sent
        assert "CONVERSATION HISTORY" in prompt_sent

    def test_renders_history_with_role_labels(self):
        client = _make_client(SAFE_DEFAULT)
        preprocessor = QueryPreprocessor(client)
        history = [
            {"role": "user", "content": "find me sci-fi"},
            {"role": "assistant", "content": "How about Inception?"},
        ]
        preprocessor.parse("more emotional", conversation_history=history)
        prompt_sent = client.generate_json.call_args.args[0]
        assert "User: find me sci-fi" in prompt_sent
        assert "Assistant: How about Inception?" in prompt_sent

    def test_truncates_history_to_last_5(self):
        client = _make_client(SAFE_DEFAULT)
        preprocessor = QueryPreprocessor(client)
        history = [{"role": "user", "content": f"msg{i}"} for i in range(8)]
        preprocessor.parse("hi", conversation_history=history)
        prompt_sent = client.generate_json.call_args.args[0]
        assert "msg7" in prompt_sent
        assert "msg2" not in prompt_sent
