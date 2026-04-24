"""FastAPI application entry point for CineRAG backend."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.auth.router import router as auth_router
from backend.chat.router import router as chat_router
from backend.config import APP_NAME, CORS_ORIGINS
from backend.database import init_db
from backend.movies.router import router as movies_router

logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(movies_router)
app.include_router(chat_router)


@app.on_event("startup")
def startup() -> None:
    init_db()

    app.state.retriever = None
    app.state.llm_client = None
    app.state.chat_service = None

    try:
        from backend.chat.service import ChatService  # type: ignore
        from backend.rag.llm_client import OllamaClient  # type: ignore
        from backend.rag.retriever import MovieRetriever  # type: ignore

        app.state.retriever = MovieRetriever()
        app.state.llm_client = OllamaClient()
        app.state.chat_service = ChatService(app.state.retriever, app.state.llm_client)
    except Exception as exc:
        logger.warning("RAG services were not initialized on startup: %s", exc)
