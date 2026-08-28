"""Local HTTP status server that OpenCode plugins poll for dictation state.

Endpoints (127.0.0.1 only):
  GET /state?since=N -> {"status", "event", "id", "text", "fetches"}
    status: idle | recording | transcribing
    event:  null | "transcript"  (only when id > since)
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


class VoiceBridgeState:
    """Thread-safe state shared between the app and the HTTP handler."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = "idle"
        self._event_id = 0
        self._event_kind: str | None = None
        self._event_text = ""
        self._fetches = 0

    def set_status(self, status: str) -> None:
        with self._lock:
            self._status = status

    def publish_transcript(self, text: str) -> int:
        with self._lock:
            self._event_id += 1
            self._event_kind = "transcript"
            self._event_text = text
            self._fetches = 0
            return self._event_id

    def snapshot(self, since: int) -> dict:
        with self._lock:
            has_event = self._event_kind is not None and self._event_id > since
            if has_event:
                self._fetches += 1
            return {
                "status": self._status,
                "event": self._event_kind if has_event else None,
                "id": self._event_id,
                "text": self._event_text if has_event else "",
                "fetches": self._fetches,
            }

    def fetches_for(self, event_id: int) -> int:
        with self._lock:
            if event_id != self._event_id:
                return -1
            return self._fetches


def _make_handler(state: VoiceBridgeState):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/state":
                self.send_error(404)
                return
            params = parse_qs(parsed.query)
            try:
                since = int(params.get("since", ["0"])[0])
            except ValueError:
                since = 0
            body = json.dumps(state.snapshot(since)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args) -> None:  # noqa: ANN002
            pass

    return Handler


class VoiceBridgeServer:
    """Runs the loopback-only state server in a daemon thread."""

    def __init__(self, port: int) -> None:
        self.state = VoiceBridgeState()
        self._port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return
        self._server = ThreadingHTTPServer(("127.0.0.1", self._port), _make_handler(self.state))
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    @property
    def port(self) -> int:
        return self._port
