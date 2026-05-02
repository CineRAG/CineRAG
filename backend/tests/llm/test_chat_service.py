"""Unit tests for ChatService orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

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
    assert out["debug"]["num_candidates_after_filter"] == 5
    retriever.search_by_title.assert_not_called()


def test_general_question_skips_retrieval_and_returns_no_recs():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    parsed = {
        "intent": "general_question",
        "reference_movie": None,
        "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
        "refinement": None,
    }
    gen_result = {"response_text": "Here's an explanation.", "recommendations": []}
    _stub_pipeline(service, parsed, "should not be called", gen_result)

    out = service.process_chat(
        user_message="What's neo-noir?",
        session_id="s2",
        user_id=42,
        watched_movie_ids=set(),
    )

    assert out["recommendations"] == []
    assert out["response_text"] == "Here's an explanation."
    assert out["debug"]["retrieval_method"] == "skipped"
    assert out["debug"]["expanded_query"] == ""
    assert out["debug"]["num_candidates_before_filter"] == 0
    retriever.retrieve_hybrid.assert_not_called()
    service.expander.expand.assert_not_called()


def test_refine_previous_falls_back_to_fresh_query():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    parsed = {
        "intent": "refine_previous",
        "reference_movie": None,
        "attributes": {"genre": None, "mood": None, "era": "1990s", "exclusions": None},
        "refinement": "more recent",
    }
    gen_result = {"response_text": "ok", "recommendations": []}
    _stub_pipeline(service, parsed, "fresh expanded", gen_result)

    out = service.process_chat(
        user_message="more recent please",
        session_id="s3",
        user_id=42,
        watched_movie_ids=set(),
    )

    # Pipeline ran end-to-end, but parsed_intent in debug was rewritten
    assert out["debug"]["parsed_intent"]["intent"] == "find_by_mood"
    assert out["debug"]["parsed_intent"]["refinement"] is None


def test_reference_movie_resolution_uses_search_by_title():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    parsed = {
        "intent": "find_similar",
        "reference_movie": "Inception",
        "attributes": {"genre": None, "mood": "emotional", "era": None, "exclusions": None},
        "refinement": None,
    }
    gen_result = {"response_text": "ok", "recommendations": []}
    _stub_pipeline(service, parsed, "expanded", gen_result)

    service.process_chat(
        user_message="like Inception but emotional",
        session_id="s4",
        user_id=42,
        watched_movie_ids=set(),
    )

    retriever.search_by_title.assert_called_once_with("Inception", top_k=1)
    args, kwargs = service.expander.expand.call_args
    assert kwargs.get("reference_movie_data") is not None or (len(args) >= 2 and args[1] is not None)


def test_watched_filter_drops_watched_movies():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    parsed = {
        "intent": "find_by_mood",
        "reference_movie": None,
        "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None},
        "refinement": None,
    }
    gen_result = {"response_text": "ok", "recommendations": []}
    _stub_pipeline(service, parsed, "expanded", gen_result)

    out = service.process_chat(
        user_message="x",
        session_id="s5",
        user_id=42,
        watched_movie_ids={"456789", "975900"},  # Inception + Titanic
    )

    assert out["debug"]["num_candidates_before_filter"] == 5
    assert out["debug"]["num_candidates_after_filter"] == 3


def test_connection_error_returns_graceful_response():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    service.preprocessor = MagicMock()
    service.preprocessor.parse.side_effect = ConnectionError("ollama down")

    out = service.process_chat(
        user_message="x",
        session_id="s6",
        user_id=42,
        watched_movie_ids=set(),
    )

    assert out["recommendations"] == []
    assert "unavailable" in out["response_text"].lower()
    assert out["session_id"] == "s6"


def test_timeout_error_returns_graceful_response():
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    service.preprocessor = MagicMock()
    service.preprocessor.parse.side_effect = TimeoutError("slow")

    out = service.process_chat(
        user_message="x",
        session_id="s7",
        user_id=42,
        watched_movie_ids=set(),
    )

    assert out["recommendations"] == []
    assert "unavailable" in out["response_text"].lower()


def test_exclusion_attribute_drops_matching_genres_before_generation():
    """Real reranker (Week 2 swap) honours `attributes.exclusions`.

    Stand-in `_rerank` ignored parsed_intent and would have passed all 5
    candidates to the generator. After swapping to `backend.rag.reranker.rerank`,
    candidates whose genres match the exclusion must be removed.
    """
    retriever = _make_retriever()
    llm = _make_llm()
    service = ChatService(retriever=retriever, llm_client=llm)
    parsed = {
        "intent": "find_by_mood",
        "reference_movie": None,
        "attributes": {
            "genre": None,
            "mood": None,
            "era": None,
            "exclusions": "no romance",
        },
        "refinement": None,
    }
    gen_result = {"response_text": "ok", "recommendations": []}
    _stub_pipeline(service, parsed, "expanded", gen_result)

    service.process_chat(
        user_message="x",
        session_id="s8",
        user_id=42,
        watched_movie_ids=set(),
    )

    reranked = service.generator.generate.call_args.kwargs["reranked_movies"]
    ids = {m["movie_id"] for m in reranked}
    # Romance-tagged movies must be dropped; only Inception + Arrival survive.
    assert ids == {"456789", "567890"}, (
        f"expected only non-romance movies, got {ids}"
    )
