"""Ollama HTTP client wrapper.

Person B's foundational module — every other Person B stage uses an OllamaClient
instance to call the local Mistral model.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 120


class OllamaClient:
    """Thin wrapper around Ollama's local HTTP API.

    See Contest/interface_contract.md §3 for the canonical signature.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise TimeoutError(
                f"Ollama request exceeded {REQUEST_TIMEOUT_SECONDS}s"
            ) from exc
        except requests.ConnectionError as exc:
            raise ConnectionError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        body = response.json()
        return body["response"]
