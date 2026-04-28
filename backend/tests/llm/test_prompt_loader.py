"""Unit tests for the prompt loader helper."""
from __future__ import annotations

import pytest

from backend.rag._prompt_loader import load_prompt


def test_loads_existing_prompt_file(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "demo.txt").write_text("hello {name}", encoding="utf-8")

    monkeypatch.setattr("backend.rag._prompt_loader.PROMPTS_DIR", prompts_dir)
    out = load_prompt("demo")
    assert out == "hello {name}"


def test_loads_fresh_each_call_no_cache(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    f = prompts_dir / "demo.txt"
    f.write_text("v1", encoding="utf-8")
    monkeypatch.setattr("backend.rag._prompt_loader.PROMPTS_DIR", prompts_dir)

    assert load_prompt("demo") == "v1"
    f.write_text("v2", encoding="utf-8")
    assert load_prompt("demo") == "v2"


def test_raises_filenotfound_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.rag._prompt_loader.PROMPTS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_prompt("nope")
