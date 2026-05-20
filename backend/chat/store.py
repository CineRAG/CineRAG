"""Persistence helpers for chats and messages."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from backend.chat.models import Chat, ChatMessage
from backend.chat.schemas import ChatHistoryMessage, ChatSummary


def _truncate_title(text: str, limit: int = 120) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "New conversation"
    return cleaned if len(cleaned) <= limit else f"{cleaned[: limit - 1]}…"


def get_or_create_chat(db: Session, *, user_id: int, chat_id: str) -> Chat:
    chat = db.query(Chat).filter_by(id=chat_id, user_id=user_id).first()
    if chat:
        return chat
    chat = Chat(id=chat_id, user_id=user_id, title="New conversation")
    db.add(chat)
    db.flush()
    return chat


def save_chat_turn(
    db: Session,
    *,
    user_id: int,
    chat_id: str,
    user_message: str,
    assistant_message: str,
    metadata: dict | None = None,
) -> Chat:
    chat = get_or_create_chat(db, user_id=user_id, chat_id=chat_id)
    now = datetime.utcnow()

    if chat.title == "New conversation":
        chat.title = _truncate_title(user_message)

    db.add(
        ChatMessage(
            chat_id=chat_id,
            role="user",
            content=user_message,
        )
    )
    db.add(
        ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content=assistant_message,
            metadata_json=json.dumps(metadata or {}, default=str),
        )
    )
    chat.updated_at = now
    db.flush()
    return chat


def list_user_chats(db: Session, user_id: int) -> list[ChatSummary]:
    chats = (
        db.query(Chat)
        .options(selectinload(Chat.messages))
        .filter_by(user_id=user_id)
        .order_by(Chat.updated_at.desc())
        .all()
    )
    summaries: list[ChatSummary] = []
    for chat in chats:
        message_count = len(chat.messages)
        preview = chat.title
        if message_count:
            first_user = next((m for m in chat.messages if m.role == "user"), None)
            if first_user:
                preview = _truncate_title(first_user.content)
        summaries.append(
            ChatSummary(
                id=chat.id,
                title=chat.title,
                preview=preview,
                updated_at=chat.updated_at,
                message_count=message_count,
            )
        )
    return summaries


def get_chat_messages(db: Session, *, user_id: int, chat_id: str) -> list[ChatHistoryMessage] | None:
    chat = db.query(Chat).filter_by(id=chat_id, user_id=user_id).first()
    if not chat:
        return None

    rows = (
        db.query(ChatMessage)
        .filter_by(chat_id=chat_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [_row_to_history_message(row) for row in rows]


def get_recent_conversation_history(
    db: Session, *, user_id: int, chat_id: str, limit: int = 5
) -> list[dict]:
    rows = (
        db.query(ChatMessage)
        .join(Chat, ChatMessage.chat_id == Chat.id)
        .filter(Chat.id == chat_id, Chat.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def parse_message_metadata(raw: str | None) -> tuple[list, dict | None]:
    if not raw:
        return [], None
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return [], None
    if not isinstance(meta, dict):
        return [], None
    recs = meta.get("recommendations") or []
    debug = meta.get("debug")
    return recs if isinstance(recs, list) else [], debug if isinstance(debug, dict) else None


def _row_to_history_message(row: ChatMessage) -> ChatHistoryMessage:
    recs, debug = parse_message_metadata(row.metadata_json)
    return ChatHistoryMessage(
        id=row.id,
        role=row.role,
        content=row.content,
        created_at=row.created_at,
        recommendations=recs,
        debug=debug,
    )
