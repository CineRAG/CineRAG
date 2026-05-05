"""Chat endpoint shell and integration wiring for the RAG orchestrator."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth.utils import get_current_user
from backend.chat.schemas import ChatRequest, ChatResponse
from backend.database import get_db
from backend.movies.models import ConversationMessage, WatchedMovieDB

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


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # 1) Collect watched movie IDs for filtering.
    watched = db.query(WatchedMovieDB).filter_by(user_id=user_id).all()
    watched_ids = {item.movie_id for item in watched}

    # 2) Load last 5 conversation messages in this session.
    history_rows = (
        db.query(ConversationMessage)
        .filter_by(user_id=user_id, session_id=payload.session_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(5)
        .all()
    )
    conversation_history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    # 3) Call Person B's orchestrator once integrated.
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
        )
    except (ConnectionError, TimeoutError, ImportError, OSError) as exc:
        logger.exception("Chat pipeline dependency failed for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat pipeline dependency failed: {type(exc).__name__}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected chat pipeline failure for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat pipeline failed unexpectedly: {type(exc).__name__}",
        ) from exc

    if not isinstance(result, dict):
        logger.error("Chat service returned non-dict response for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat service returned an invalid response type: {type(result).__name__}",
        )

    debug_payload = result.get("debug")
    if result.get("response_text") == SERVICE_UNAVAILABLE_TEXT or (
        isinstance(debug_payload, dict) and debug_payload.get("parsed_intent") is None
    ):
        logger.error("Chat service returned its dependency-unavailable fallback for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service dependencies are unavailable. Check Ollama, retriever indices, and /api/health.",
        )

    try:
        response = ChatResponse.model_validate(result)
    except ValidationError as exc:
        logger.exception("Chat service returned invalid response for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat service returned an invalid response: {exc.errors()[0]['msg']}",
        ) from exc

    # 4) Persist user/assistant messages.
    db.add(
        ConversationMessage(
            user_id=user_id,
            session_id=payload.session_id,
            role="user",
            content=payload.message,
        )
    )
    db.add(
        ConversationMessage(
            user_id=user_id,
            session_id=payload.session_id,
            role="assistant",
            content=response.response_text,
            metadata_json=json.dumps(result.get("debug", {}), default=str),
        )
    )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to persist conversation history for session_id=%r", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not persist conversation history: {type(exc).__name__}",
        ) from exc

    return response
