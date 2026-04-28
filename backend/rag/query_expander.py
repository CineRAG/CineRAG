"""Stage 2 - expand parsed intent into a 3-5 sentence semantic query.

See Contest/interface_contract.md §3 for signature.
"""
from __future__ import annotations

import json
import logging

from backend.rag._prompt_loader import load_prompt
from backend.rag.llm_client import OllamaClient

logger = logging.getLogger(__name__)


def _build_reference_section(reference_movie_data: dict | None) -> str:
    if not reference_movie_data:
        return ""
    title = reference_movie_data.get("title", "(unknown)")
    genres = ", ".join(reference_movie_data.get("genres", []))
    plot = reference_movie_data.get("plot_summary", "")
    return f"Reference movie: \"{title}\" ({genres}) - {plot}"


class QueryExpander:
    """Stage 2: expand intent into rich semantic query text."""

    def __init__(self, llm_client: OllamaClient) -> None:
        self.llm_client = llm_client

    def expand(
        self,
        parsed_intent: dict,
        reference_movie_data: dict | None = None,
    ) -> str:
        template = load_prompt("expansion")
        prompt = template.format(
            parsed_intent_json=json.dumps(parsed_intent, ensure_ascii=False),
            reference_section=_build_reference_section(reference_movie_data),
        )
        raw = self.llm_client.generate(prompt, temperature=0.7)
        return raw.strip()
