import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("httpx")

from llm.client import OpenAICompatibleClient
from llm.config import LLMConfig


class _StreamingHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_lines = []
    response_body = ""
    captured_body = None
    captured_headers = None
    captured_path = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        type(self).captured_body = json.loads(body)
        type(self).captured_headers = dict(self.headers)
        type(self).captured_path = self.path

        self.send_response(type(self).response_status)
        if type(self).response_status >= 400:
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(type(self).response_body.encode("utf-8"))
            self.wfile.flush()
            return

        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for line in type(self).response_lines:
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

    def log_message(self, format, *args):
        return


def _run_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_stream_chat_builds_openai_compatible_payload():
    config = LLMConfig(
        base_url="https://example.test",
        model=None,
        api_key="secret",
        chat_path="/smart",
        reasoning_effort="low",
        timeout_sec=30,
        max_tokens=256,
        temperature=0.1,
    )
    client = OpenAICompatibleClient(config)

    payload = client.build_payload([{"role": "user", "content": "hello"}])

    assert payload == {
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "temperature": 0.1,
        "max_tokens": 256,
    }


def test_stream_chat_handles_sse_and_malformed_lines():
    handler = _StreamingHandler
    handler.response_status = 200
    handler.response_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
        'data: {not-json}\n\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
        'data: [DONE]\n\n',
    ]
    handler.response_body = ""
    handler.captured_body = None
    handler.captured_headers = None
    handler.captured_path = None
    server, thread = _run_server(handler)
    try:
        config = LLMConfig(
            base_url=f"http://127.0.0.1:{server.server_address[1]}",
            model=None,
            api_key="secret",
            chat_path="/smart",
            reasoning_effort="low",
        )
        client = OpenAICompatibleClient(config)

        chunks = list(client.stream_chat([{"role": "user", "content": "hello"}]))

        assert chunks == ["Hello", " world"]
        assert handler.captured_path == "/smart"
        assert "model" not in handler.captured_body
        assert handler.captured_body["stream"] is True
        assert handler.captured_headers["Authorization"] == "Bearer secret"
        assert handler.captured_headers["X-Reasoning-Effort"] == "low"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def test_stream_chat_raises_on_http_error():
    handler = _StreamingHandler
    handler.response_status = 400
    handler.response_lines = []
    handler.response_body = "bad request"
    server, thread = _run_server(handler)
    try:
        config = LLMConfig(
            base_url=f"http://127.0.0.1:{server.server_address[1]}",
            model=None,
            api_key=None,
            chat_path="/smart",
            reasoning_effort=None,
        )
        client = OpenAICompatibleClient(config)

        with pytest.raises(RuntimeError, match="HTTP 400"):
            list(client.stream_chat([{"role": "user", "content": "hello"}]))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)
