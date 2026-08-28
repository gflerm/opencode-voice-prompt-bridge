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
    image = {"saved": None, "restored": []}
    fg = {"hwnd": None}

    class FakeUser32:
        def GetForegroundWindow(self):  # noqa: N802
            return fg["hwnd"]

    monkeypatch.setattr(tui, "_user32", FakeUser32())
    monkeypatch.setattr(tui, "activate_window", lambda hwnd: calls.append(("activate", hwnd)))
    monkeypatch.setattr(tui, "_ctrl_v", lambda: calls.append(("paste",)))
    monkeypatch.setattr(tui, "_enter", lambda: calls.append(("enter",)))
    monkeypatch.setattr(tui, "_type_text", lambda text, **kw: calls.append(("type", text)))
    monkeypatch.setattr(tui, "_save_clipboard_image", lambda: image["saved"])
    monkeypatch.setattr(tui, "_restore_clipboard_image", lambda data: image["restored"].append(data) or True)
    monkeypatch.setattr(tui.pyperclip, "paste", lambda: clipboard["current"])
    monkeypatch.setattr(tui.pyperclip, "copy", lambda text: clipboard.__setitem__("current", text))
    monkeypatch.setattr(tui.time, "sleep", lambda _s: None)
    return calls, clipboard, image, fg


def test_send_pastes_and_submits(fake_tui):
    calls, clipboard, image, fg = fake_tui
    fg["hwnd"] = 12345
    tui.send_to_window(12345, "hello there", settle_s=0.0)
    assert calls == [("activate", 12345), ("paste",), ("enter",)]
    assert clipboard["current"] == "old-clipboard"  # restored
    assert image["restored"] == []


def test_send_empty_text_rejected(fake_tui):
    calls, _clipboard, _image, _fg = fake_tui
    with pytest.raises(tui.TuiError):
        tui.send_to_window(12345, "   ")
    assert calls == []


def test_send_without_target_window(fake_tui):
    calls, _clipboard, _image, _fg = fake_tui
    with pytest.raises(tui.TuiError, match="no target window"):
        tui.send_to_window(0, "hello")
    assert calls == []


def test_send_keeps_clipboard_when_restore_disabled(fake_tui):
    calls, clipboard, _image, fg = fake_tui
    fg["hwnd"] = 99
    tui.send_to_window(99, "text", restore_clipboard=False, settle_s=0.0)
    assert clipboard["current"] == "text"
    assert calls == [("activate", 99), ("paste",), ("enter",)]


def test_send_preserves_image_clipboard(fake_tui):
    calls, clipboard, image, fg = fake_tui
    fg["hwnd"] = 7
    image["saved"] = b"dib-bytes"
    tui.send_to_window(7, "describe this", settle_s=0.0)
    assert calls == [("activate", 7), ("paste",), ("enter",)]
    assert image["restored"] == [b"dib-bytes"]
    # text restore must not overwrite the restored image
    assert clipboard["current"] == "describe this" or clipboard["current"] != "old-clipboard"


def test_send_fails_loudly_when_focus_not_captured(fake_tui):
    calls, clipboard, image, fg = fake_tui
    fg["hwnd"] = 999  # activation never reaches the target
    with pytest.raises(tui.TuiError, match="could not focus"):
        tui.send_to_window(12345, "hello", settle_s=0.0)
    assert ("paste",) not in calls and ("enter",) not in calls
    assert image["restored"] == []  # nothing consumed the clipboard


def test_type_mode_types_without_clipboard_or_enter(fake_tui):
    calls, clipboard, image, fg = fake_tui
    fg["hwnd"] = 55
    tui.send_to_window(55, "hello world", press_enter=False, input_method="type", settle_s=0.0)
    assert calls == [("activate", 55), ("type", "hello world")]
    assert clipboard["current"] == "old-clipboard"  # untouched
    assert image["saved"] is None or image["restored"] == []


def test_type_mode_with_enter(fake_tui):
    calls, _clipboard, _image, fg = fake_tui
    fg["hwnd"] = 55
    tui.send_to_window(55, "go", press_enter=True, input_method="type", settle_s=0.0)
    assert calls == [("activate", 55), ("type", "go"), ("enter",)]


def test_unknown_input_method_rejected(fake_tui):
    calls, _clipboard, _image, fg = fake_tui
    fg["hwnd"] = 55
    with pytest.raises(tui.TuiError, match="unknown input_method"):
        tui.send_to_window(55, "hi", input_method="carrier-pigeon")
    assert calls == []
