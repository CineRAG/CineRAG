"""Ollama HTTP client wrapper.

Person B's foundational module — every other Person B stage uses an OllamaClient
instance to call the local Mistral model.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 120
JSON_PARSE_RETRY_HINT = "\n\nRespond with valid JSON only, no markdown backticks."


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
        url = f"{self.base_url}/api/generate"
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            logger.error(
                "Ollama timeout after %ds calling %s", REQUEST_TIMEOUT_SECONDS, url
            )
            raise TimeoutError(
                f"Ollama request exceeded {REQUEST_TIMEOUT_SECONDS}s"
            ) from exc
        except requests.ConnectionError as exc:
            logger.error("Ollama connection failed at %s: %s", self.base_url, exc)
            raise ConnectionError(
                f"Could not reach Ollama at {self.base_url}: {exc}"
            ) from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.error(
                "Ollama returned HTTP %s for %s: %s", status, url, exc
            )
            raise ConnectionError(
                f"Ollama returned HTTP {status} from {url}: {exc}"
            ) from exc
        body = response.json()
        return body["response"]

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
    ) -> dict:
        first_raw = self.generate(prompt, system_prompt, temperature)
        try:
            return _parse_json_strict(first_raw)
        except ValueError:
            logger.warning("LLM JSON parse failed on first attempt; retrying once")

        retry_prompt = prompt + JSON_PARSE_RETRY_HINT
        second_raw = self.generate(retry_prompt, system_prompt, temperature)
        try:
            return _parse_json_strict(second_raw)
        except ValueError:
            logger.error("LLM JSON parse failed twice; returning error dict")
            return {"error": "json_parse_failed", "raw_response": second_raw}


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _parse_json_strict(text: str) -> dict:
    """Strip markdown code fences and parse strict JSON. Raises ValueError on failure."""
    cleaned = _FENCE_RE.sub("", text).strip()
    return json.loads(cleaned)
