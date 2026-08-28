"""TUI bridge: paste dictated text into the previously focused window.

Captures the foreground window when recording starts; on send it is
re-focused, the text is pasted via clipboard (Ctrl+V) and submitted
with Enter. Works with interactive TUIs like the OpenCode terminal and
any ordinary text input.
"""

from __future__ import annotations

import sys
import time

import pyperclip

if sys.platform == "win32":
    import ctypes

    _user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


class TuiError(RuntimeError):
    """Raised when the paste handoff cannot be performed."""


def capture_foreground() -> int:
    """Return the current foreground window handle (0 if none)."""
    if sys.platform != "win32":
        return 0
    return int(_user32.GetForegroundWindow())


def activate_window(hwnd: int) -> None:
    """Bring a window to the foreground (ALT-tap unlocks SetForegroundWindow)."""
    if sys.platform != "win32" or not hwnd:
        return
    _user32.keybd_event(VK_MENU, 0, 0, 0)
    _user32.SetForegroundWindow(hwnd)
    _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)


def _key(vk: int, up: bool = False) -> None:
    _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP if up else 0, 0)


def _ctrl_v() -> None:
    _key(VK_CONTROL)
    _key(VK_V)
    _key(VK_V, up=True)
    _key(VK_CONTROL, up=True)


def _enter() -> None:
    _key(VK_RETURN)
    _key(VK_RETURN, up=True)


def send_to_window(
    hwnd: int,
    text: str,
    restore_clipboard: bool = True,
    settle_s: float = 0.25,
) -> None:
    """Paste text into the given window and press Enter.

    The previous clipboard content is saved and restored after the
    target application has consumed the paste.
    """
    if not text.strip():
        raise TuiError("refusing to paste an empty prompt")
    if sys.platform != "win32":
        raise TuiError("TUI bridge is only implemented on Windows")
    if not hwnd:
        raise TuiError("no target window captured (nothing was focused when recording started)")

    previous = None
    try:
        previous = pyperclip.paste()
    except Exception:
        pass

    pyperclip.copy(text)
    activate_window(hwnd)
    time.sleep(settle_s)
    _ctrl_v()
    time.sleep(settle_s)
    _enter()

    if restore_clipboard and previous is not None:
        time.sleep(settle_s)
        try:
            pyperclip.copy(previous)
        except Exception:
            pass
