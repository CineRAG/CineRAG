"""Unit tests for QueryExpander (Stage 2)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.rag.query_expander import QueryExpander


def _client(text: str):
    c = MagicMock()
    c.generate.return_value = text
    return c


PARSED_INTENT_NO_REF = {
    "intent": "find_by_mood",
    "reference_movie": None,
    "attributes": {"genre": "sci-fi", "mood": "thoughtful", "era": None, "exclusions": "no horror"},
    "refinement": None,
}

PARSED_INTENT_WITH_REF = {
    "intent": "find_similar",
    "reference_movie": "Inception",
    "attributes": {"genre": None, "mood": "emotional", "era": None, "exclusions": None},
    "refinement": None,
}

INCEPTION_DATA = {
    "movie_id": "456789",
    "title": "Inception",
    "year": 2010,
    "genres": ["Science Fiction", "Thriller"],
    "plot_summary": "Dom Cobb steals secrets from people's subconscious during dream states.",
}


class TestExpand:
    def test_returns_string_without_reference_data(self):
        client = _client("A thoughtful sci-fi film with quiet wonder.")
        expander = QueryExpander(client)
        out = expander.expand(PARSED_INTENT_NO_REF)
        assert isinstance(out, str)
        assert out == "A thoughtful sci-fi film with quiet wonder."

    def test_returns_string_with_reference_data(self):
        client = _client("A psychological thriller with emotional weight.")
        expander = QueryExpander(client)
        out = expander.expand(PARSED_INTENT_WITH_REF, reference_movie_data=INCEPTION_DATA)
        assert isinstance(out, str)
        assert "psychological" in out

    def test_prompt_contains_reference_block_when_provided(self):
        client = _client("ok")
        expander = QueryExpander(client)
        expander.expand(PARSED_INTENT_WITH_REF, reference_movie_data=INCEPTION_DATA)
        sent = client.generate.call_args.args[0]
        assert "Inception" in sent
        assert "dream states" in sent

    def test_prompt_omits_reference_block_when_absent(self):
        client = _client("ok")
        expander = QueryExpander(client)
        expander.expand(PARSED_INTENT_NO_REF)
        sent = client.generate.call_args.args[0]
        assert "Reference movie" not in sent

    def test_strips_whitespace_from_output(self):
        client = _client("\n  A clean description.   \n\n")
        expander = QueryExpander(client)
        out = expander.expand(PARSED_INTENT_NO_REF)
        assert out == "A clean description."
