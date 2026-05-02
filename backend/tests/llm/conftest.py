"""Shared pytest fixtures and path setup for Person B's LLM test suite."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure `from backend.rag... import ...` works when running pytest from any cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
