"""Pydantic schemas for chat endpoint request/response."""

from __future__ import annotations

from datetime import datetime

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
    silent: bool = False


class ChatResponse(BaseModel):
    session_id: str
    response_text: str
    recommendations: list[Recommendation]
    debug: ChatDebug


class ChatHistoryMessage(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    recommendations: list[Recommendation] = Field(default_factory=list)
    debug: dict | None = None


class ChatSummary(BaseModel):
    id: str
    title: str
    preview: str
    updated_at: datetime
    message_count: int


class ChatsListResponse(BaseModel):
    chats: list[ChatSummary]


class ChatDetailResponse(BaseModel):
    id: str
    title: str
    messages: list[ChatHistoryMessage]


class CreateChatResponse(BaseModel):
    id: str
    title: str
    created_at: datetime


# Legacy aliases (session_id == chat id)
class ChatSessionSummary(BaseModel):
    session_id: str
    preview: str
    updated_at: datetime
    message_count: int
    title: str | None = None


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionSummary]


class ChatSessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatHistoryMessage]
