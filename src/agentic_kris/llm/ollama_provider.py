"""Local LLM backend via the Ollama REST API.

Talks to a running Ollama server (default http://localhost:11434) over plain
HTTP, so it needs no SDK beyond ``requests``. Keeps the whole system able to run
fully offline when paired with the in-memory retriever.
"""
from __future__ import annotations

import json
from typing import Iterator, List

import requests

from .base import LLMProvider, Message


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, host: str, model: str, timeout: int = 120):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
        }
        resp = requests.post(
            f"{self.host}/api/chat",
            json=payload,
            stream=True,
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = (data.get("message") or {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break

    def _raise_for_status(self, resp: "requests.Response") -> None:
        """Raise with Ollama's own error message (e.g. 'model not found').

        Ollama returns a JSON ``{"error": "..."}`` body with a 404 when a model
        isn't pulled; surfacing it turns an opaque HTTP 404 into an actionable
        message in the UI.
        """
        if resp.ok:
            return
        detail = ""
        try:
            detail = (resp.json() or {}).get("error", "")
        except ValueError:
            detail = (resp.text or "").strip()[:200]
        hint = ""
        if resp.status_code == 404 and "model" in detail.lower():
            hint = (
                f" — pull it with `ollama pull {self.model}`, or pick a model you "
                f"already have (`ollama list`)."
            )
        raise RuntimeError(
            f"Ollama request to {resp.url} failed ({resp.status_code}): "
            f"{detail or resp.reason}{hint}"
        )

    def health_check(self) -> str:
        resp = requests.get(f"{self.host}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        have = any(self.model in m for m in models)
        status = "available" if have else "NOT pulled"
        return f"ollama reachable at {self.host}; model '{self.model}' {status}"
