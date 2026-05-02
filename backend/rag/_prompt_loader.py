"""Plain-text prompt loader for Person B's RAG stages.

Loads `.txt` files from `backend/rag/prompts/` fresh on every call so prompt
edits take effect without restarting Python. No caching is intentional - Week 1
prompt iteration is the bulk of quality work.
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Read `<PROMPTS_DIR>/<name>.txt` and return its contents."""
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")
