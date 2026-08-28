"""ReviewManager queueing tests with a stub window (no real Tk)."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from transcriber import Transcript
from ui_review import ReviewManager, ReviewPayload


def make_transcript(text: str) -> Transcript:
    return Transcript(
        text=text, language="en", avg_logprob=-0.2, no_speech_prob=0.05,
        duration_s=2.0, inference_s=0.2, device="cuda", compute_type="float16",
    )


def make_payload(text: str) -> ReviewPayload:
    return ReviewPayload(text=text, original=text, status="test")


class StubStatus:
    def __init__(self) -> None:
        self.last = {}

    def config(self, **kwargs) -> None:
        self.last.update(kwargs)


class StubWindow:
    def __init__(self, root, payload, callbacks) -> None:
        self.payload = payload
        self.callbacks = callbacks
        self.status = StubStatus()
        self._closed = False
        self.finished_ok = False
        self.error_detail: str | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    def finish_ok(self, detail: str) -> None:
        self.finished_ok = True
        self._closed = True

    def finish_error(self, detail: str) -> None:
        self.error_detail = detail


def make_manager():
    windows: list[StubWindow] = []
    sent: list[tuple[str, list]] = []

    def factory(root, payload, callbacks):
        win = StubWindow(root, payload, callbacks)
        windows.append(win)
        return win

    manager = ReviewManager(
        root=None, on_send=lambda text, pairs: sent.append((text, pairs)), window_factory=factory
    )
    return manager, windows, sent


def test_present_opens_window():
    manager, windows, _sent = make_manager()
    manager.present(make_payload("hello"))
    assert len(windows) == 1
    assert windows[0].payload.text == "hello"
    assert manager.is_open


def test_present_while_open_queues():
    manager, windows, _sent = make_manager()
    manager.present(make_payload("first"))
    manager.present(make_payload("second"))
    assert len(windows) == 1
    manager._handle_close("")
    assert len(windows) == 2
    assert windows[1].payload.text == "second"


def test_send_callback_and_success_closes():
    manager, windows, sent = make_manager()
    manager.present(make_payload("hello"))
    windows[0].callbacks.on_send("hello edited", [("hello", "hello edited")])
    assert sent == [("hello edited", [("hello", "hello edited")])]
    manager.send_succeeded()
    assert windows[0].finished_ok
    assert not manager.is_open


def test_send_failure_shows_error_keeps_window():
    manager, windows, sent = make_manager()
    manager.present(make_payload("hello"))
    windows[0].callbacks.on_send("hello", [])
    manager.send_failed("executable not found")
    assert windows[0].error_detail == "executable not found"
    assert manager.is_open
