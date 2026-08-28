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
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalSize.restype = ctypes.c_size_t
    _kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]

CF_DIB = 8
GMEM_MOVEABLE = 0x0002

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


def _save_clipboard_image() -> bytes | None:
    """Return raw CF_DIB bytes if an image is on the clipboard, else None."""
    if sys.platform != "win32" or not _user32.OpenClipboard(0):
        return None
    try:
        if not _user32.IsClipboardFormatAvailable(CF_DIB):
            return None
        handle = _user32.GetClipboardData(CF_DIB)
        if not handle:
            return None
        size = _kernel32.GlobalSize(handle)
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.string_at(ptr, size)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def _restore_clipboard_image(data: bytes) -> bool:
    if sys.platform != "win32" or not _user32.OpenClipboard(0):
        return False
    try:
        _user32.EmptyClipboard()
        handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return False
        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            _kernel32.GlobalUnlock(handle)
        _user32.SetClipboardData(CF_DIB, handle)
        return True
    finally:
        _user32.CloseClipboard()


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

    image_data = _save_clipboard_image()
    previous = None
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = None

    pyperclip.copy(text)
    activate_window(hwnd)
    time.sleep(settle_s)
    _ctrl_v()
    time.sleep(settle_s)
    _enter()

    if restore_clipboard:
        if image_data is not None:
            _restore_clipboard_image(image_data)
        elif previous:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass
