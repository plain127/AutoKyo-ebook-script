from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from autokyo.mcp_server import AutokyoMCPServer


class _ServerState:
    def __init__(self, *, default_config_path: str | Path) -> None:
        self.mcp = AutokyoMCPServer(default_config_path=default_config_path)
        self.lock = threading.Lock()


class _MCPHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        default_config_path: str | Path,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.state = _ServerState(default_config_path=default_config_path)


class _MCPHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _MCPHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        if self._request_path() == "/healthz":
            self._send_bytes(
                HTTPStatus.OK,
                b"ok\n",
                content_type="text/plain; charset=utf-8",
            )
            return

        if self._request_path() != "/mcp":
            self._send_status_only(HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(b": autokyo streamable-http\n\n")
        self.wfile.flush()

    def do_POST(self) -> None:  # noqa: N802
        if self._request_path() != "/mcp":
            self._send_status_only(HTTPStatus.NOT_FOUND)
            return

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                {"error": "Missing Content-Length header"},
            )
            return

        try:
            body_size = int(content_length)
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid Content-Length header"},
            )
            return

        payload = self.rfile.read(body_size)
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"Invalid JSON body: {exc}"},
            )
            return

        if not isinstance(message, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "JSON body must be an object"},
            )
            return

        with self.server.state.lock:
            if "id" in message:
                response = self.server.state.mcp._handle_request(message)
                self._send_json(HTTPStatus.OK, response)
                return

            self.server.state.mcp._handle_notification(message)

        self._send_status_only(HTTPStatus.ACCEPTED)

    def do_DELETE(self) -> None:  # noqa: N802
        if self._request_path() != "/mcp":
            self._send_status_only(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _request_path(self) -> str:
        return urlsplit(self.path).path

    def _send_status_only(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_bytes(self, status: HTTPStatus, payload: bytes, *, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, body, content_type="application/json")


def run_streamable_http_server(
    *,
    default_config_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> int:
    server = _MCPHTTPServer(
        (host, port),
        _MCPHTTPRequestHandler,
        default_config_path=default_config_path,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0
