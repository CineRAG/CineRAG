"""Unit tests for OllamaClient (Person B Stage shared)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
import requests

from backend.rag.llm_client import OllamaClient


def _make_response(json_body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


class TestGenerate:
    def test_returns_response_field_from_ollama(self):
        client = OllamaClient()
        fake = _make_response({"response": "Hello world"})
        with patch("backend.rag.llm_client.requests.post", return_value=fake) as mock_post:
            out = client.generate("Hi there")
        assert out == "Hello world"
        mock_post.assert_called_once()

    def test_posts_correct_payload_and_url(self):
        client = OllamaClient(base_url="http://localhost:11434", model="mistral")
        fake = _make_response({"response": "ok"})
        with patch("backend.rag.llm_client.requests.post", return_value=fake) as mock_post:
            client.generate("prompt text", system_prompt="sys", temperature=0.5, max_tokens=512)
        url = mock_post.call_args.args[0]
        payload = mock_post.call_args.kwargs["json"]
        assert url == "http://localhost:11434/api/generate"
        assert payload["model"] == "mistral"
        assert payload["prompt"] == "prompt text"
        assert payload["system"] == "sys"
        assert payload["stream"] is False
        assert payload["options"] == {"temperature": 0.5, "num_predict": 512}
        assert mock_post.call_args.kwargs["timeout"] == 120

    def test_default_temperature_and_max_tokens(self):
        client = OllamaClient()
        fake = _make_response({"response": "ok"})
        with patch("backend.rag.llm_client.requests.post", return_value=fake) as mock_post:
            client.generate("p")
        opts = mock_post.call_args.kwargs["json"]["options"]
        assert opts["temperature"] == 0.7
        assert opts["num_predict"] == 1024

    def test_raises_connection_error_on_connection_failure(self):
        client = OllamaClient()
        with patch(
            "backend.rag.llm_client.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            with pytest.raises(ConnectionError):
                client.generate("p")

    def test_raises_timeout_error_on_request_timeout(self):
        client = OllamaClient()
        with patch(
            "backend.rag.llm_client.requests.post",
            side_effect=requests.Timeout("slow"),
        ):
            with pytest.raises(TimeoutError):
                client.generate("p")

    def test_raises_connection_error_on_http_error(self):
        client = OllamaClient()
        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error", response=bad_resp
        )
        with patch(
            "backend.rag.llm_client.requests.post",
            return_value=bad_resp,
        ):
            with pytest.raises(ConnectionError):
                client.generate("p")

    def test_strips_trailing_slash_from_base_url(self):
        client = OllamaClient(base_url="http://localhost:11434/")
        fake = _make_response({"response": "ok"})
        with patch("backend.rag.llm_client.requests.post", return_value=fake) as mock_post:
            client.generate("p")
        url = mock_post.call_args.args[0]
        assert url == "http://localhost:11434/api/generate"
