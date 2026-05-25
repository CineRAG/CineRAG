"""Unit tests for ResponseGenerator (Stage 6)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.rag.generator import (
    DETERMINISTIC_FALLBACK_TEXT,
    FALLBACK_TOP_K,
    PLOT_PREVIEW_LEN,
    ResponseGenerator,
    _clean_plot_summary,
    _plot_preview,
    _safe_per_movie_explanation,
    _smart_truncate,
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

    def test_plot_preview_is_cleaned_and_truncated_at_sentence_boundary(self):
        client = _client_json(_good_picks_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        movie = next(m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == "345678")
        # Clean Netflix-style plots pass through _clean_plot_summary unchanged,
        # so this asserts the contract end-to-end: the rendered preview is
        # whatever _plot_preview yields on the source text.
        assert out["recommendations"][0]["plot_preview"] == _plot_preview(movie["plot_summary"])
        assert len(out["recommendations"][0]["plot_preview"]) <= PLOT_PREVIEW_LEN

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

    def test_llm_explanation_that_copies_plot_is_replaced(self):
        # Lazy LLM lifts the first sentence of Inception's plot verbatim.
        inception_plot = next(
            m["plot_summary"] for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == "456789"
        )
        copied = inception_plot[:140]  # well above the 60-char run threshold
        payload = {
            "response_text": "Here is a pick.",
            "picks": [
                {
                    "movie_id": "456789",
                    "explanation": copied,
                    "match_reasons": ["dream logic"],
                }
            ],
        }
        client = _client_json(payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="dream movie",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        rec = out["recommendations"][0]
        # Replacement must not be the copied plot text, must not be a slice of
        # the plot at all, and must not equal the plot_preview rendered below.
        assert rec["explanation"] != copied
        assert rec["explanation"] not in inception_plot
        assert rec["plot_preview"] == _plot_preview(inception_plot)
        assert rec["explanation"] != rec["plot_preview"]

    def test_llm_explanation_that_paraphrases_passes_through(self):
        # Genuine paraphrase that synthesizes concepts — must NOT be flagged.
        original = (
            "A meditation on memory, guilt, and the boundary between dreams and "
            "reality — fits your request for layered psychological storytelling."
        )
        payload = {
            "response_text": "Here is a pick.",
            "picks": [
                {
                    "movie_id": "456789",
                    "explanation": original,
                    "match_reasons": ["dream logic"],
                }
            ],
        }
        client = _client_json(payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="dream movie",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert out["recommendations"][0]["explanation"] == original

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

    def test_accepts_integer_movie_ids_from_llm(self):
        """The prompt's wording (digits only, no quotes) makes the LLM emit
        JSON numbers, so picks arrive as int. Validation must coerce to string
        before looking them up against the string-keyed candidate dict —
        otherwise EVERY pick is dropped and the deterministic fallback fires
        100% of the time, which is what was happening in production."""
        payload = {
            "response_text": "Three picks.",
            "picks": [
                {"movie_id": 975900, "explanation": "real 1", "match_reasons": []},
                {"movie_id": 234567, "explanation": "real 2", "match_reasons": []},
                {"movie_id": 345678, "explanation": "real 3", "match_reasons": []},
            ],
        }
        client = _client_json(payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert client.generate_json.call_count == 1, (
            "Should not retry — int IDs must resolve on first attempt"
        )
        assert [r["movie_id"] for r in out["recommendations"]] == [
            "975900", "234567", "345678",
        ], "Integer picks must be coerced to canonical string IDs"
        # And the LLM's real explanations must survive (no fallback rewrite).
        assert out["recommendations"][0]["explanation"] == "real 1"

    def test_accepts_mixed_int_and_str_movie_ids(self):
        payload = {
            "response_text": "Mixed types.",
            "picks": [
                {"movie_id": "975900", "explanation": "str pick", "match_reasons": []},
                {"movie_id": 234567, "explanation": "int pick", "match_reasons": []},
            ],
        }
        client = _client_json(payload)
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        assert [r["movie_id"] for r in out["recommendations"]] == ["975900", "234567"]


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
        # IDs are rendered quoted so the LLM emits them as JSON strings, not
        # bare numbers. The validation layer is type-tolerant, but lining up
        # prompt and validation reduces fallback firing in the first place.
        for movie in MOCK_RETRIEVAL_RESULTS:
            assert f'"{movie["movie_id"]}"' in retry_prompt

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

    def test_fallback_never_echoes_llm_text_or_plot_slice(self):
        # Deterministic fallback must never echo the LLM's hallucinated text
        # (e.g., "fake1" attached to invalid IDs) and must not contain plot text
        # (would duplicate plot_preview on the card).
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        for rec in out["recommendations"]:
            assert "fake" not in rec["explanation"]
            source = next(
                m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == rec["movie_id"]
            )
            assert rec["explanation"] not in source["plot_summary"]

    def test_fallback_explanations_are_distinct_across_cards(self):
        """Bug fix: previously every fallback card got the same static string,
        making the three recommendation cards read like xeroxes. The per-movie
        explanation must vary across cards so the UI does not look broken."""
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        explanations = [r["explanation"] for r in out["recommendations"]]
        assert len(explanations) == FALLBACK_TOP_K
        assert len(set(explanations)) == FALLBACK_TOP_K, (
            f"Expected {FALLBACK_TOP_K} distinct explanations, got {explanations}"
        )

    def test_fallback_explanation_mentions_movie_metadata(self):
        """The per-movie fallback should weave in the movie's year and primary
        genre so the user sees concrete grounding, not a generic placeholder."""
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        for rec in out["recommendations"]:
            source = next(
                m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == rec["movie_id"]
            )
            assert str(source["year"]) in rec["explanation"]
            primary_genre = source["genres"][0].lower()
            assert primary_genre in rec["explanation"].lower()

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

    def test_deterministic_fallback_plot_preview_is_populated_and_distinct(self):
        # plot_preview must carry the real plot slice as citation/evidence and
        # must NOT match the explanation text (avoids the duplication bug
        # introduced when explanation was itself a plot slice).
        client = _client_json_sequence(_all_invalid_payload(), _all_invalid_payload())
        gen = ResponseGenerator(client)
        out = gen.generate(
            user_message="x",
            reranked_movies=MOCK_RETRIEVAL_RESULTS,
            parsed_intent=PARSED_INTENT_RECOMMEND,
        )
        for rec in out["recommendations"]:
            source = next(
                m for m in MOCK_RETRIEVAL_RESULTS if m["movie_id"] == rec["movie_id"]
            )
            assert rec["plot_preview"] == _plot_preview(source["plot_summary"])
            assert rec["plot_preview"] != rec["explanation"]

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


class TestSafePerMovieExplanation:
    """Unit tests for the per-movie deterministic explanation builder."""

    def test_includes_year_and_primary_genre(self):
        movie = {
            "movie_id": "1",
            "title": "Foo",
            "year": 2011,
            "genres": ["Drama", "Romance"],
            "plot_summary": "p",
        }
        out = _safe_per_movie_explanation(movie, {}, index=0)
        assert "2011" in out
        assert "drama" in out.lower()

    def test_weaves_in_mood_attribute_when_present(self):
        movie = {"movie_id": "1", "title": "Foo", "year": 2011, "genres": ["Drama"]}
        out = _safe_per_movie_explanation(movie, {"mood": "bittersweet"}, index=0)
        assert "bittersweet" in out.lower()

    def test_index_varies_intro_phrasing(self):
        movie = {"movie_id": "1", "title": "Foo", "year": 2011, "genres": ["Drama"]}
        outs = [_safe_per_movie_explanation(movie, {}, index=i) for i in range(3)]
        assert len(set(outs)) == 3

    def test_no_metadata_still_returns_distinct_safe_string(self):
        movie = {"movie_id": "1", "title": "Foo"}
        out = _safe_per_movie_explanation(movie, {}, index=0)
        assert out.strip() != ""
        assert "plot summary" in out.lower()

    def test_never_includes_plot_text(self):
        movie = {
            "movie_id": "1",
            "title": "Foo",
            "year": 2011,
            "genres": ["Drama"],
            "plot_summary": "A young couple from different social backgrounds fall in love.",
        }
        out = _safe_per_movie_explanation(movie, {"mood": "tense"}, index=0)
        assert "young couple" not in out.lower()
        assert "social backgrounds" not in out.lower()


class TestCleanPlotSummary:
    """Unit tests for the Wikipedia-markup stripper applied to plot_preview."""

    def test_empty_input_returns_empty(self):
        assert _clean_plot_summary("") == ""
        assert _clean_plot_summary(None) == ""  # type: ignore[arg-type]

    def test_no_op_on_clean_netflix_style_text(self):
        s = "A young couple from different social backgrounds fall deeply in love."
        assert _clean_plot_summary(s) == s

    def test_strips_cite_web_template(self):
        s = "Melodrama about a university student's experiences with love. Synopsis based on {{cite web}}"
        out = _clean_plot_summary(s)
        assert "{{" not in out
        assert "cite web" not in out
        # Trailing "Synopsis based on" with nothing after it gets cleaned too.
        assert not out.lower().endswith("synopsis based on")

    def test_strips_inline_template_mid_text(self):
        s = "She returned home {{citation needed}} and confronted her past."
        out = _clean_plot_summary(s)
        assert "citation needed" not in out
        assert "She returned home" in out
        assert "confronted her past" in out

    def test_strips_ref_tags_pair_and_self_closing(self):
        s = 'A war drama<ref name="Smith 1999">Smith p. 12</ref> set in the trenches.<ref name="Jones"/>'
        out = _clean_plot_summary(s)
        assert "<ref" not in out
        assert "Smith" not in out
        assert "war drama" in out
        assert "trenches" in out

    def test_strips_section_headers(self):
        s = "== Plot ==\nA man wakes up. === Cast === The lead is played by..."
        out = _clean_plot_summary(s)
        assert "==" not in out
        assert "A man wakes up" in out

    def test_strips_file_and_image_links(self):
        s = "A war movie [[File:Tank.jpg|thumb|A tank]] set in 1944. [[Image:Map.png]]"
        out = _clean_plot_summary(s)
        assert "[[" not in out
        assert "File:" not in out
        assert "war movie" in out

    def test_extracts_piped_link_display_text(self):
        s = "She studied at [[Cambridge University|Cambridge]] before the war."
        out = _clean_plot_summary(s)
        assert "[[" not in out
        assert "Cambridge" in out
        assert "Cambridge University" not in out

    def test_strips_html_comments(self):
        s = "A spy thriller. <!-- TODO: rewrite this --> The hero defects."
        out = _clean_plot_summary(s)
        assert "<!--" not in out
        assert "TODO" not in out
        assert "spy thriller" in out
        assert "hero defects" in out

    def test_collapses_whitespace(self):
        s = "Line one.\n\n\nLine    two.\t\tLine three."
        out = _clean_plot_summary(s)
        assert "\n" not in out
        assert "  " not in out
        assert "Line one. Line two. Line three." == out

    def test_real_world_passion_portrait_style(self):
        # From Ömer's screenshot — exact-ish leakage pattern.
        s = "Melodrama about a university student's experiences with love and political ideologies.Synopsis based on {{cite web}}"
        out = _clean_plot_summary(s)
        assert "{{" not in out
        assert "cite web" not in out
        assert "Melodrama" in out
        assert "political ideologies" in out


class TestSmartTruncate:
    """Unit tests for sentence-boundary-aware truncation."""

    def test_short_text_passes_through_unchanged(self):
        s = "A short plot."
        assert _smart_truncate(s, 100) == s

    def test_truncates_at_last_sentence_end_when_feasible(self):
        s = "First sentence. Second sentence is here. Third sentence runs much longer than the others to push past the limit."
        out = _smart_truncate(s, 50)
        # Last sentence end within window is after "is here."
        assert out.endswith(".")
        assert out == "First sentence. Second sentence is here."

    def test_falls_back_to_word_boundary_when_no_sentence_end(self):
        # No periods in the first 50 chars — must trim at last space + ellipsis.
        s = "This is a long sentence that runs on and on without any punctuation marks at all in sight"
        out = _smart_truncate(s, 50)
        assert out.endswith("...")
        assert not out[:-3].endswith(" ")
        assert len(out) <= 50

    def test_hard_cuts_when_no_useful_boundary(self):
        # No spaces at all, no sentence ends.
        s = "Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        out = _smart_truncate(s, 20)
        assert out.endswith("...")
        assert len(out) <= 20

    def test_does_not_chase_too_short_a_sentence_cut(self):
        # Only sentence-end is right at the start; cutting there would drop
        # most of the content. Should fall back to word/hard cut instead.
        s = "OK. Then a much much longer second part that has no further punctuation marks anywhere visible at all"
        out = _smart_truncate(s, 60)
        # Must not have cut at the early "OK." — that's only 3 chars, below threshold.
        assert out != "OK."
        assert len(out) > 30


class TestPlotPreviewIntegration:
    """End-to-end behaviour of _plot_preview = clean + truncate."""

    def test_clean_plot_under_limit_returns_full_text(self):
        s = "A clean short synopsis under three hundred chars."
        assert _plot_preview(s) == s

    def test_garbage_template_cleaned_before_truncation(self):
        s = "A romance about memory and time {{cite web|title=foo}} that unfolds across decades."
        out = _plot_preview(s)
        assert "{{" not in out
        assert "cite web" not in out

    def test_result_never_exceeds_max_length(self):
        s = "Long sentence. " * 100
        out = _plot_preview(s)
        assert len(out) <= PLOT_PREVIEW_LEN
