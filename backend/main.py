"""FastAPI application entry point for CineRAG backend."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.auth.router import router as auth_router
from backend.chat.router import router as chat_router
from backend.config import APP_NAME, BM25_INDEX_PATH, CHROMA_DB_PATH, CORS_ORIGINS
from backend.database import SessionLocal, init_db
from backend.movies.router import router as movies_router

logging.basicConfig(level=logging.INFO)
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
    app.state.startup_status = {
        "database": {"status": "ok", "detail": "SQLite schema initialized"},
        "retriever": {"status": "unavailable", "detail": "Not initialized"},
        "llm_client": {"status": "unavailable", "detail": "Not initialized"},
        "chat_service": {"status": "unavailable", "detail": "Not initialized"},
    }

    try:
        from backend.chat.service import ChatService  # type: ignore
        from backend.rag.llm_client import OllamaClient  # type: ignore
        from backend.rag.retriever import MovieRetriever  # type: ignore

        app.state.retriever = MovieRetriever(
            chroma_db_path=CHROMA_DB_PATH,
            bm25_index_path=BM25_INDEX_PATH,
        )
        app.state.startup_status["retriever"] = {
            "status": "ok",
            "detail": "MovieRetriever initialized",
        }

        #app.state.llm_client = OllamaClient()
        app.state.llm_client = OllamaClient(model="gpt-oss:120b-cloud")
        app.state.startup_status["llm_client"] = {
            "status": "ok",
            "detail": "OllamaClient initialized",
        }

        app.state.chat_service = ChatService(app.state.retriever, app.state.llm_client)
        app.state.startup_status["chat_service"] = {
            "status": "ok",
            "detail": "ChatService initialized",
        }
        logger.info("RAG services initialized successfully")
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        logger.exception("RAG services were not initialized on startup: %s", detail)
        if app.state.retriever is None:
            app.state.startup_status["retriever"] = {"status": "error", "detail": detail}
        if app.state.llm_client is None:
            app.state.startup_status["llm_client"] = {"status": "error", "detail": detail}
        if app.state.chat_service is None:
            app.state.startup_status["chat_service"] = {"status": "error", "detail": detail}


@app.get("/api/health", tags=["health"])
def health() -> dict:
    status = getattr(app.state, "startup_status", {})
    database_status = "ok"
    database_detail = "Database connection is healthy"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        database_status = "error"
        database_detail = f"{type(exc).__name__}: {exc}"

    components = {
        "database": {"status": database_status, "detail": database_detail},
        "retriever": status.get("retriever", {"status": "unknown", "detail": "Startup has not run"}),
        "llm_client": status.get("llm_client", {"status": "unknown", "detail": "Startup has not run"}),
        "chat_service": status.get("chat_service", {"status": "unknown", "detail": "Startup has not run"}),
    }
    overall = "ok" if all(item["status"] == "ok" for item in components.values()) else "degraded"

    return {
        "status": overall,
        "components": components,
        "paths": {
            "chroma_db_path": CHROMA_DB_PATH,
            "bm25_index_path": BM25_INDEX_PATH,
        },
    }
