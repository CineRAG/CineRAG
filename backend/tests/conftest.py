# backend/tests/conftest.py
import sys
from pathlib import Path

# Make backend/ importable when pytest runs from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
