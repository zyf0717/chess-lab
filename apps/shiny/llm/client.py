from __future__ import annotations

import json
import threading
from typing import Any, Iterator

try:
    import httpx
except ImportError:  # pragma: no cover - dependency is optional at import time
    httpx = None

from .config import LLMConfig


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def build_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "messages": messages,
            "stream": True,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if self._config.model:
            payload["model"] = self._config.model
        return payload

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        stop_event: threading.Event | None = None,
    ) -> Iterator[str]:
        if httpx is None:
            raise RuntimeError("LLM commentary requires httpx to be installed.")

        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        if self._config.reasoning_effort:
            headers["X-Reasoning-Effort"] = self._config.reasoning_effort

        url = f"{self._config.base_url}{self._config.chat_path}"
        payload = self.build_payload(messages)
        timeout = httpx.Timeout(self._config.timeout_sec)

        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", errors="ignore").strip()
                    detail = body or response.reason_phrase or "unknown error"
                    raise RuntimeError(
                        f"LLM request failed with HTTP {response.status_code}: {detail}"
                    )

                for data in _iter_sse_data(response.iter_lines()):
                    if stop_event is not None and stop_event.is_set():
                        return
                    if data == "[DONE]":
                        break
                    try:
                        payload_item = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = _extract_delta_text(payload_item)
                    if delta:
                        yield delta


def _iter_sse_data(lines: Iterator[str]) -> Iterator[str]:
    parts: list[str] = []
    for line in lines:
        if line == "":
            if parts:
                yield "\n".join(parts)
                parts = []
            continue
        if line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        parts.append(line[5:].lstrip())
    if parts:
        yield "\n".join(parts)


def _extract_delta_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)
        return "".join(chunks)
    message = choices[0].get("message") or {}
    fallback = message.get("content")
    return fallback if isinstance(fallback, str) else ""


def httpx_available() -> bool:
    return httpx is not None
