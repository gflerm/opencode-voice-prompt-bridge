"""TUI bridge tests (win32 calls and clipboard are faked)."""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters import tui


@pytest.fixture()
def fake_tui(monkeypatch):
    calls = []
    clipboard = {"current": "old-clipboard"}

    monkeypatch.setattr(tui, "activate_window", lambda hwnd: calls.append(("activate", hwnd)))
    monkeypatch.setattr(tui, "_ctrl_v", lambda: calls.append(("paste",)))
    monkeypatch.setattr(tui, "_enter", lambda: calls.append(("enter",)))
    monkeypatch.setattr(tui.pyperclip, "paste", lambda: clipboard["current"])
    monkeypatch.setattr(tui.pyperclip, "copy", lambda text: clipboard.__setitem__("current", text))
    monkeypatch.setattr(tui.time, "sleep", lambda _s: None)
    return calls, clipboard


def test_send_pastes_and_submits(fake_tui):
    calls, clipboard = fake_tui
    tui.send_to_window(12345, "hello there", settle_s=0.0)
    assert calls == [("activate", 12345), ("paste",), ("enter",)]
    assert clipboard["current"] == "old-clipboard"  # restored


def test_send_empty_text_rejected(fake_tui):
    calls, _clipboard = fake_tui
    with pytest.raises(tui.TuiError):
        tui.send_to_window(12345, "   ")
    assert calls == []


def test_send_without_target_window(fake_tui):
    calls, _clipboard = fake_tui
    with pytest.raises(tui.TuiError, match="no target window"):
        tui.send_to_window(0, "hello")
    assert calls == []


def test_send_keeps_clipboard_when_restore_disabled(fake_tui):
    calls, clipboard = fake_tui
    tui.send_to_window(99, "text", restore_clipboard=False, settle_s=0.0)
    assert clipboard["current"] == "text"
    assert calls == [("activate", 99), ("paste",), ("enter",)]
