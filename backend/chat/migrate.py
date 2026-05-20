"""One-time migration from legacy `conversations` table to `chats` / `chat_messages`."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.chat.models import Chat, ChatMessage
from backend.chat.store import _truncate_title
from backend.database import SessionLocal, engine

logger = logging.getLogger(__name__)


def migrate_legacy_conversations(db: Session) -> int:
    """Copy rows from `conversations` into chats/chat_messages. Returns migrated session count."""
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return 0
    if db.query(Chat).count() > 0:
        return 0

    from backend.movies.models import ConversationMessage

    rows = (
        db.query(ConversationMessage)
        .order_by(ConversationMessage.session_id, ConversationMessage.created_at.asc())
        .all()
    )
    if not rows:
        return 0

    sessions: dict[str, dict] = {}
    for row in rows:
        bucket = sessions.setdefault(
            row.session_id,
            {
                "user_id": row.user_id,
                "title": "New conversation",
                "created_at": row.created_at,
                "updated_at": row.created_at,
                "messages": [],
            },
        )
        if row.role == "user" and bucket["title"] == "New conversation":
            bucket["title"] = _truncate_title(row.content)
        if row.created_at:
            if bucket["created_at"] is None or row.created_at < bucket["created_at"]:
                bucket["created_at"] = row.created_at
            if bucket["updated_at"] is None or row.created_at > bucket["updated_at"]:
                bucket["updated_at"] = row.created_at
        bucket["messages"].append(row)

    for chat_id, data in sessions.items():
        chat = Chat(
            id=chat_id,
            user_id=data["user_id"],
            title=data["title"],
            created_at=data["created_at"] or datetime.utcnow(),
            updated_at=data["updated_at"] or datetime.utcnow(),
        )
        db.add(chat)
        for legacy in data["messages"]:
            db.add(
                ChatMessage(
                    chat_id=chat_id,
                    role=legacy.role,
                    content=legacy.content,
                    metadata_json=legacy.metadata_json,
                    created_at=legacy.created_at or datetime.utcnow(),
                )
            )

    db.commit()
    count = len(sessions)
    logger.info("Migrated %d legacy conversation session(s) into chats table", count)
    return count


def run_migrations() -> None:
    with SessionLocal() as db:
        migrate_legacy_conversations(db)
