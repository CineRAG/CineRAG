"""Chat endpoint shell and integration wiring for the RAG orchestrator."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.auth.utils import get_current_user
from backend.chat.schemas import ChatRequest, ChatResponse
from backend.database import get_db
from backend.movies.models import ConversationMessage, WatchedMovieDB

router = APIRouter(tags=["chat"])


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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat service is not available yet")

    result = chat_service.process_chat(
        user_message=payload.message,
        session_id=payload.session_id,
        user_id=user_id,
        watched_movie_ids=watched_ids,
        conversation_history=conversation_history,
    )

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
            content=result.get("response_text", ""),
            metadata_json=json.dumps(result.get("debug", {})),
        )
    )
    db.commit()

    return ChatResponse.model_validate(result)
