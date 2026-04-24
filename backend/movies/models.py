"""SQLAlchemy models for watched movies and conversation history."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func

from backend.database import Base


class WatchedMovieDB(Base):
    __tablename__ = "watched_movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    movie_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    genres = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "movie_id"),)


class ConversationMessage(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
