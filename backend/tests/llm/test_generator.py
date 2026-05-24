"""Unit tests for ResponseGenerator (Stage 6)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.rag.generator import (
    DETERMINISTIC_FALLBACK_TEXT,
    FALLBACK_TOP_K,
    SAFE_INTRO_TEXT,
    ResponseGenerator,
)
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


def _client_json_sequence(*payloads):
    c = MagicMock()
    c.generate_json.side_effect = list(payloads)
    c.generate.return_value = "ok"
    return c


def _all_invalid_payload():
    return {
        "response_text": "Here are three picks.",
        "picks": [
            {"movie_id": "111111", "explanation": "fake1", "match_reasons": []},
            {"movie_id": "222222", "explanation": "fake2", "match_reasons": []},
            {"movie_id": "333333", "explanation": "fake3", "match_reasons": []},
        ],
    }


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

    def test_accepts_picks_with_integer_movie_ids(self):
        # The LLM frequently emits movie_id as a bare JSON number (because the
        # prompt asks for digits). Python parses that as int; by_id keys are str.
        # Without coercion every pick gets dropped, the system falls back to
        # deterministic, and we never see the LLM-written reasoning.
        # Mock data movie_ids are strings ("456789"); LLM here returns 456789.
        bad_payload = {
            "response_text": "Pick.",
            "picks": [
                {"movie_id": 456789, "explanation": "dreams", "match_reasons": []},
            ],
        }
        client = _client_json(bad_payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        # Must resolve to Inception, not fall back.
        assert len(out["recommendations"]) == 1
        assert out["recommendations"][0]["movie_id"] == "456789"
        # No retry needed — the first attempt succeeded after coercion.
        assert client.generate_json.call_count == 1

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
        # At least one valid pick → no retry needed.
        assert client.generate_json.call_count == 1


class TestRetryAndFallback:
    """Spec §2-§3: retry on all-invalid picks, then deterministic top-K fallback."""

    def test_retries_when_first_attempt_returns_only_invalid_ids(self):
        valid_payload = _good_picks_payload()
        client = _client_json_sequence(_all_invalid_payload(), valid_payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert client.generate_json.call_count == 2
        assert len(out["recommendations"]) == 2
        assert {r["movie_id"] for r in out["recommendations"]} == {"345678", "567890"}
        assert out["response_text"] == valid_payload["response_text"]

    def test_retries_when_first_attempt_returns_json_parse_error(self):
        error_payload = {"error": "json_parse_failed", "raw_response": "junk"}
        valid_payload = _good_picks_payload()
        client = _client_json_sequence(error_payload, valid_payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert client.generate_json.call_count == 2
        assert len(out["recommendations"]) == 2

    def test_retry_prompt_contains_allowed_movie_ids(self):
        client = _client_json_sequence(_all_invalid_payload(), _good_picks_payload())
        gen = ResponseGenerator(client)
        gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        retry_prompt = client.generate_json.call_args_list[1].args[0]
        assert "RETRY NOTICE" in retry_prompt
        for movie in MOCK_RETRIEVAL_RESULTS:
            assert f"- {movie['movie_id']}" in retry_prompt

    def test_deterministic_fallback_fires_when_both_attempts_invalid(self):
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert client.generate_json.call_count == 2
        assert len(out["recommendations"]) == FALLBACK_TOP_K
        # Top-K from MOCK_RETRIEVAL_RESULTS, in order.
        assert [r["movie_id"] for r in out["recommendations"]] == [
            "975900",
            "234567",
            "345678",
        ]
        # Response text must not claim a numeric count it can't back up.
        assert out["response_text"] == DETERMINISTIC_FALLBACK_TEXT

    def test_fallback_uses_plot_summary_for_explanation(self):
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        first = out["recommendations"][0]
        titanic_plot = MOCK_RETRIEVAL_RESULTS[0]["plot_summary"]
        # Explanation should start with the plot text, not an LLM-generated string
        # like "fake1" from the invalid payload.
        assert first["explanation"].startswith(titanic_plot[:50])
        assert "fake" not in first["explanation"]

    def test_fallback_match_reasons_reflect_parsed_intent_attributes(self):
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        reasons = out["recommendations"][0]["match_reasons"]
        # PARSED_INTENT_RECOMMEND has genre=drama, mood=thoughtful, era=None, exclusions=None.
        assert any("drama" in r.lower() for r in reasons)
        assert any("thoughtful" in r.lower() for r in reasons)

    def test_fallback_recommendations_never_empty_when_candidates_exist(self):
        """Spec invariant: fallback must never return [] when reranked_movies is non-empty."""
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS[:1],  # only Titanic
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert len(out["recommendations"]) == 1
        assert out["recommendations"][0]["movie_id"] == "975900"

    def test_deterministic_fallback_plot_preview_is_empty(self):
        # Fallback explanations are direct slices of plot — plot_preview would duplicate.
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        for rec in out["recommendations"]:
            assert rec["plot_preview"] == ""

    def test_response_text_is_consistent_when_recommendations_empty(self):
        """When recommendations is [], response_text must not promise picks."""
        gen = ResponseGenerator(_client_json({}))
        out = gen.generate(
            user_message="x",
            reranked_movies=[],
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"] == []
        text = out["response_text"].lower()
        # Should not contain numeric promises like "three movies", "two films", etc.
        assert "three movies" not in text
        assert "two movies" not in text


class TestGroundedReasoning:
    """Sanitize LLM explanations and match_reasons that reference names not in the
    candidate's plot summary or title — the leading hallucination mode for cards."""

    def _payload(self, explanation, match_reasons):
        return {
            "response_text": "Here is a pick.",
            "picks": [
                {
                    "movie_id": "456789",
                    "explanation": explanation,
                    "match_reasons": match_reasons,
                }
            ],
        }

    def test_explanation_with_director_name_is_replaced_with_plot_fallback(self):
        # Inception's plot mentions Dom Cobb but NOT Christopher Nolan.
        client = _client_json(
            self._payload(
                "Christopher Nolan crafts a layered dreamscape that fits your request.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="dream movie",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        assert "Christopher Nolan" not in rec["explanation"]
        # Fallback is built from the plot — must start with the plot text.
        inception_plot = next(
            m["plot_summary"] for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == "456789"
        )
        assert rec["explanation"].startswith(inception_plot[:30])

    def test_explanation_grounded_in_plot_passes_through_untouched(self):
        # All names in this explanation ARE in Inception's plot.
        original = "Dom Cobb steals secrets from dreams and confronts his guilt — fits your request."
        client = _client_json(self._payload(original, ["dream logic"]))
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="dream movie",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"][0]["explanation"] == original

    def test_proper_nouns_appearing_in_title_are_allowed(self):
        # "Eternal Sunshine" is in the title even though it's not in the plot summary.
        original = "Eternal Sunshine takes a couple through a memory-erasing procedure."
        client = _client_json(
            {
                "response_text": "ok",
                "picks": [
                    {
                        "movie_id": "345678",
                        "explanation": original,
                        "match_reasons": ["memory loss"],
                    }
                ],
            }
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"][0]["explanation"] == original

    def test_match_reasons_with_hallucinated_names_are_dropped(self):
        client = _client_json(
            self._payload(
                "Dom Cobb steals secrets from dreams.",
                ["Steven Spielberg vibes", "dream logic", "Hans Zimmer score"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        reasons = out["recommendations"][0]["match_reasons"]
        assert reasons == ["dream logic"]

    def test_match_reasons_all_dropped_get_replaced_with_safe_label(self):
        client = _client_json(
            self._payload(
                "Dom Cobb steals secrets from dreams.",
                ["Christopher Nolan film", "Hans Zimmer score"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        # All tags hallucinated → fallback to "retrieved match" so the card has at least one tag.
        assert out["recommendations"][0]["match_reasons"] == ["retrieved match"]

    def test_award_phrases_are_treated_as_ungrounded(self):
        client = _client_json(
            self._payload(
                "An Academy Award winner about dreams and guilt.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "Academy Award" not in out["recommendations"][0]["explanation"]

    def test_explanation_with_lowercase_directed_by_is_sanitized(self):
        # "directed by nolan" — fully lowercase, so the multi-word proper-noun
        # regex misses it. Credit-phrase detection picks up "directed by".
        client = _client_json(
            self._payload(
                "directed by nolan, this layered dream thriller fits your request.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        assert "directed by" not in rec["explanation"].lower()
        assert "nolan" not in rec["explanation"].lower()

    def test_explanation_with_starring_single_name_is_sanitized(self):
        # Single-word star name escapes the multi-word regex; "starring" catches it.
        client = _client_json(
            self._payload(
                "Starring DiCaprio as a dream thief — fits your request.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        assert "Starring" not in rec["explanation"]
        assert "DiCaprio" not in rec["explanation"]

    def test_explanation_with_screenplay_by_is_sanitized(self):
        client = _client_json(
            self._payload(
                "Screenplay by an Oscar nominee, exploring dreams and guilt.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "Screenplay by" not in out["recommendations"][0]["explanation"]

    def test_explanation_with_box_office_phrase_is_sanitized(self):
        # Commercial framing without any proper noun — only credit-phrase logic catches.
        client = _client_json(
            self._payload(
                "A box office triumph about stealing secrets from dreams.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "box office" not in out["recommendations"][0]["explanation"].lower()

    def test_explanation_with_wrong_year_is_sanitized(self):
        # Inception is year=2010 in mock data; LLM claims 1995.
        client = _client_json(
            self._payload(
                "This 1995 thriller about dream-stealers fits your request.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "1995" not in out["recommendations"][0]["explanation"]

    def test_explanation_with_matching_source_year_passes(self):
        # Year matches Inception's catalog year (2010) — grounded via metadata.
        original = "Released in 2010, this dream-layered thriller fits the request."
        client = _client_json(self._payload(original, ["dream logic"]))
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"][0]["explanation"] == original

    def test_explanation_with_decade_form_in_plot_passes(self):
        # The Notebook plot says "1940s" — decade form, no 4-digit-year token is
        # extracted from "1940s" (word boundary blocks it), so no year check fires.
        original = "Set in the 1940s, the elderly couple reconnects via a notebook."
        payload = {
            "response_text": "Here is a pick.",
            "picks": [
                {
                    "movie_id": "234567",
                    "explanation": original,
                    "match_reasons": ["timeless romance"],
                }
            ],
        }
        client = _client_json(payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"][0]["explanation"] == original

    def test_match_reason_with_credit_phrase_is_dropped(self):
        client = _client_json(
            self._payload(
                "Dom Cobb steals secrets from dreams.",
                ["dream logic", "directed by spielberg", "memory and guilt"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        reasons = out["recommendations"][0]["match_reasons"]
        assert "directed by spielberg" not in reasons
        assert "dream logic" in reasons
        assert "memory and guilt" in reasons

    def test_match_reason_with_wrong_year_is_dropped(self):
        client = _client_json(
            self._payload(
                "Dom Cobb steals secrets from dreams.",
                ["dream logic", "set in 1995", "memory and guilt"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        reasons = out["recommendations"][0]["match_reasons"]
        assert "set in 1995" not in reasons
        assert "dream logic" in reasons

    def test_plot_preview_is_empty_when_explanation_replaced_by_plot_fallback(self):
        # When the sanitizer replaces an ungrounded explanation with a plot snippet,
        # the card would otherwise render the same plot text twice (explanation +
        # plot_preview blockquote). Suppress plot_preview in that case.
        client = _client_json(
            self._payload(
                "Christopher Nolan crafts a layered dreamscape that fits your request.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        # Sanitizer fired (no Nolan in plot) → explanation is plot-derived.
        assert "Christopher Nolan" not in rec["explanation"]
        # plot_preview must be empty to avoid duplication on the card.
        assert rec["plot_preview"] == ""

    def test_plot_preview_is_empty_when_attribution_phrase_triggers_fallback(self):
        client = _client_json(
            self._payload(
                "A box office triumph about stealing secrets from dreams.",
                ["dream logic"],
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        assert "box office" not in rec["explanation"].lower()
        assert rec["plot_preview"] == ""

    def test_plot_preview_is_kept_when_explanation_passes_grounding(self):
        # Grounded LLM explanation is paraphrased, NOT a plot slice — show plot_preview
        # alongside as a citation.
        original = "Dom Cobb steals secrets from dreams and confronts his guilt."
        client = _client_json(self._payload(original, ["dream logic"]))
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        assert rec["explanation"] == original
        inception_plot = next(
            m["plot_summary"] for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == "456789"
        )
        assert rec["plot_preview"] == inception_plot[:300]


class TestResponseTextGrounding:
    """Sanitize the LLM-written intro paragraph (response_text). It's general
    across all picks, so we can't plot-ground it — we block credit/award
    attribution and multi-word proper nouns that aren't any candidate title."""

    @staticmethod
    def _payload_with_intro(intro: str) -> dict:
        return {
            "response_text": intro,
            "picks": [
                {
                    "movie_id": "456789",
                    "explanation": "Dom Cobb steals secrets from dreams.",
                    "match_reasons": ["dream logic"],
                }
            ],
        }

    def test_response_text_with_director_attribution_is_replaced(self):
        client = _client_json(
            self._payload_with_intro(
                "Three films directed by Christopher Nolan for your taste."
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["response_text"] == SAFE_INTRO_TEXT

    def test_response_text_with_award_attribution_is_replaced(self):
        client = _client_json(
            self._payload_with_intro("Three Oscar-winning thrillers for your taste.")
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "Oscar" not in out["response_text"]
        assert out["response_text"] == SAFE_INTRO_TEXT

    def test_response_text_with_proper_noun_outside_titles_is_replaced(self):
        # "Christopher Nolan" isn't any candidate title — multi-word name flagged.
        client = _client_json(
            self._payload_with_intro(
                "Here are three from Christopher Nolan's library."
            )
        )
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert "Christopher Nolan" not in out["response_text"]

    def test_response_text_mentioning_candidate_title_passes(self):
        # "Inception" is a candidate title — allowed.
        original = "I've selected Inception for you based on the dream angle."
        client = _client_json(self._payload_with_intro(original))
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["response_text"] == original

    def test_response_text_clean_passes_through(self):
        original = "Here are some thoughtful picks that match your request."
        client = _client_json(self._payload_with_intro(original))
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["response_text"] == original

    def test_response_text_grounding_runs_on_retry_path_too(self):
        # First attempt fails (all-invalid IDs), retry returns a hallucinated intro.
        # Sanitization must fire on the retry result as well, not only the first.
        hallucinated_retry = {
            "response_text": "Three Oscar-winning thrillers for your taste.",
            "picks": [
                {
                    "movie_id": "456789",
                    "explanation": "Dom Cobb steals secrets from dreams.",
                    "match_reasons": ["dream logic"],
                }
            ],
        }
        client = _client_json_sequence(_all_invalid_payload(), hallucinated_retry)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["response_text"] == SAFE_INTRO_TEXT
        assert len(out["recommendations"]) == 1
