"""Stage 1 — parse user intent into a structured ParsedIntent.

See Contest/interface_contract.md §1 (ParsedIntent shape) and §3 (function signature).
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from backend.rag._prompt_loader import load_prompt
from backend.rag.llm_client import OllamaClient

logger = logging.getLogger(__name__)

VALID_INTENTS = {"find_similar", "find_by_mood", "refine_previous", "general_question"}

SAFE_DEFAULT_PARSED_INTENT: dict[str, Any] = {
    "intent": "find_by_mood",
    "reference_movie": None,
    "attributes": {"genre": None, "mood": None, "era": None, "exclusions": None,  "min_year": None, "max_year": None},
    "refinement": None,
}

REQUIRED_KEYS = {"intent", "reference_movie", "attributes", "refinement"}
REQUIRED_ATTR_KEYS = {"genre", "mood", "era", "exclusions"}


def _render_history(history: list[dict] | None) -> str:
    if not history:
        return "(none)"
    last_five = history[-5:]
    lines = []
    for turn in last_five:
        role = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


def _is_well_formed(d: dict) -> bool:
    if not REQUIRED_KEYS.issubset(d.keys()):
        return False
    attrs = d.get("attributes")
    if not isinstance(attrs, dict):
        return False
    return REQUIRED_ATTR_KEYS.issubset(attrs.keys())


def _copy_safe_default() -> dict:
    """Return a fresh deep copy so callers can mutate safely."""
    return copy.deepcopy(SAFE_DEFAULT_PARSED_INTENT)


class QueryPreprocessor:
    """Stage 1: parse user intent from raw message + conversation history."""

    def __init__(self, llm_client: OllamaClient) -> None:
        self.llm_client = llm_client

    def parse(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        template = load_prompt("parsing")
        prompt = template.format(
            user_message=user_message,
            conversation_history=_render_history(conversation_history),
        )
        result = self.llm_client.generate_json(prompt)

        if "error" in result:
            logger.warning("Preprocessor falling back to safe default (LLM JSON parse failed)")
            return _copy_safe_default()

        if not _is_well_formed(result):
            logger.warning("Preprocessor falling back to safe default (missing required keys)")
            return _copy_safe_default()

        if result["intent"] not in VALID_INTENTS:
            logger.warning(
                "Preprocessor coercing invalid intent %r to find_by_mood", result["intent"]
            )
            result["intent"] = "find_by_mood"
          # Fill optional year fields if LLM omitted them
        attrs = result.get("attributes", {})
        attrs.setdefault("min_year", None)
        attrs.setdefault("max_year", None)
        result["attributes"] = attrs

        return result