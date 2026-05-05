"""Application configuration for CineRAG backend."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "CineRAG"

ROOT_DIR = Path(__file__).resolve().parent.parent
SQLITE_PATH = ROOT_DIR / "cinerag.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ---------------------------------------------------------------------------
# RAG data paths
# ---------------------------------------------------------------------------
LFS_DATA_DIR = Path(os.getenv("LFS_DATA_DIR", "/space_mounts/pars/data"))

RAW_DATA_DIR       = LFS_DATA_DIR / "raw"
PROCESSED_DATA_DIR = LFS_DATA_DIR / "processed"
CHROMA_DB_PATH     = os.getenv("CHROMA_DB_PATH", str(LFS_DATA_DIR / "chroma_db"))
BM25_INDEX_PATH    = os.getenv("BM25_INDEX_PATH", str(LFS_DATA_DIR / "bm25_index.pkl"))
MOVIES_JSON_PATH   = Path(os.getenv("MOVIES_JSON_PATH", str(LFS_DATA_DIR / "processed" / "movies.json")))

EVAL_DIR           = ROOT_DIR / "data" / "eval"
QUERIES_PATH       = EVAL_DIR / "queries.json"
RESULTS_PATH       = EVAL_DIR / "results.json"
