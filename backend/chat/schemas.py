"""Pydantic schemas for chat endpoint request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedIntentAttributes(BaseModel):
    genre: str | None = None
    mood: str | None = None
    era: str | None = None
    exclusions: str | None = None


class ParsedIntent(BaseModel):
    intent: str
    reference_movie: str | None = None
    attributes: ParsedIntentAttributes
    refinement: str | None = None


class Recommendation(BaseModel):
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str]
    explanation: str
    plot_preview: str
    match_reasons: list[str]


class ChatDebug(BaseModel):
    parsed_intent: ParsedIntent
    expanded_query: str
    num_candidates_before_filter: int
    num_candidates_after_filter: int
    retrieval_method: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    response_text: str
    recommendations: list[Recommendation]
    debug: ChatDebug
