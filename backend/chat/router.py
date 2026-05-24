"""Chat API — list chats, load history, send messages."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth.utils import get_current_user
from backend.chat.models import Chat
from backend.chat.schemas import (
    ChatDetailResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionHistoryResponse,
    ChatSessionSummary,
    ChatSessionsResponse,
    ChatsListResponse,
    ChatSummary,
    CreateChatResponse,
)
from backend.chat.store import (
    get_chat_messages,
    get_recent_conversation_history,
    get_recommended_movie_ids,
    list_user_chats,
    save_chat_turn,
)
from backend.database import get_db
from backend.movies.models import WatchedMovieDB

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_TEXT = "The recommendation service is temporarily unavailable. Please try again."


def _chat_service_unavailable(request: Request) -> HTTPException:
    startup_status = getattr(request.app.state, "startup_status", {})
    detail = startup_status.get("chat_service", {}).get("detail", "Chat service is not initialized")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Chat service is unavailable: {detail}",
    )


def _summary_to_legacy(summary: ChatSummary) -> ChatSessionSummary:
    return ChatSessionSummary(
        session_id=summary.id,
        preview=summary.preview,
        updated_at=summary.updated_at,
        message_count=summary.message_count,
        title=summary.title,
    )


@router.get("/api/chats", response_model=ChatsListResponse)
def list_chats(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatsListResponse:
    return ChatsListResponse(chats=list_user_chats(db, user_id))


@router.post("/api/chats", response_model=CreateChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateChatResponse:
    chat_id = str(uuid.uuid4())
    chat = Chat(id=chat_id, user_id=user_id, title="New conversation")
    db.add(chat)
    try:
        db.commit()
        db.refresh(chat)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create chat: {type(exc).__name__}",
        ) from exc
    return CreateChatResponse(id=chat.id, title=chat.title, created_at=chat.created_at)


@router.get("/api/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat(
    chat_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatDetailResponse:
    chat = db.query(Chat).filter_by(id=chat_id, user_id=user_id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    messages = get_chat_messages(db, user_id=user_id, chat_id=chat_id)
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return ChatDetailResponse(id=chat.id, title=chat.title, messages=messages)


@router.delete("/api/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_chat(
    chat_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    chat = db.query(Chat).filter_by(id=chat_id, user_id=user_id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    db.delete(chat)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete chat: {type(exc).__name__}",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/chat/sessions", response_model=ChatSessionsResponse)
def list_chat_sessions_legacy(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionsResponse:
    summaries = list_user_chats(db, user_id)
    return ChatSessionsResponse(sessions=[_summary_to_legacy(s) for s in summaries])


@router.get("/api/chat/sessions/{session_id}", response_model=ChatSessionHistoryResponse)
def get_chat_session_history_legacy(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionHistoryResponse:
    detail = get_chat(session_id, user_id, db)
    return ChatSessionHistoryResponse(session_id=detail.id, messages=detail.messages)


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    watched = db.query(WatchedMovieDB).filter_by(user_id=user_id).all()
    watched_ids = {item.movie_id for item in watched}

    conversation_history = get_recent_conversation_history(
        db, user_id=user_id, chat_id=payload.session_id, limit=5
    )
    exclude_movie_ids = get_recommended_movie_ids(
        db, user_id=user_id, chat_id=payload.session_id
    )

    chat_service = getattr(request.app.state, "chat_service", None)
    if chat_service is None or not hasattr(chat_service, "process_chat"):
        raise _chat_service_unavailable(request)

    try:
        result = chat_service.process_chat(
            user_message=payload.message,
            session_id=payload.session_id,
            user_id=user_id,
            watched_movie_ids=watched_ids,
            conversation_history=conversation_history,
            exclude_movie_ids=exclude_movie_ids,
        )
    except (ConnectionError, TimeoutError, ImportError, OSError) as exc:
        logger.exception("Chat pipeline dependency failed for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat pipeline dependency failed: {type(exc).__name__}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected chat pipeline failure for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat pipeline failed unexpectedly: {type(exc).__name__}",
        ) from exc

    if not isinstance(result, dict):
        logger.error("Chat service returned non-dict response for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat service returned an invalid response type: {type(result).__name__}",
        )

    debug_payload = result.get("debug")
    if result.get("response_text") == SERVICE_UNAVAILABLE_TEXT or (
        isinstance(debug_payload, dict) and debug_payload.get("parsed_intent") is None
    ):
        logger.error("Chat service returned its dependency-unavailable fallback for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service dependencies are unavailable. Check Ollama, retriever indices, and /api/health.",
        )

    try:
        response = ChatResponse.model_validate(result)
    except ValidationError as exc:
        logger.exception("Chat service returned invalid response for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat service returned an invalid response: {exc.errors()[0]['msg']}",
        ) from exc

    try:
        save_chat_turn(
            db,
            user_id=user_id,
            chat_id=payload.session_id,
            user_message=payload.message,
            assistant_message=response.response_text,
            metadata={
                "debug": result.get("debug", {}),
                "recommendations": result.get("recommendations", []),
            },
            persist_user_message=not payload.silent,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to persist chat for chat_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not persist conversation: {type(exc).__name__}",
        ) from exc

    return response
