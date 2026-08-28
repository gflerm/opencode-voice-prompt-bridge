"""Push-to-talk hotkey state machine + global pynput listener."""

from __future__ import annotations

import sys
import threading
from typing import Callable

from pynput import keyboard

from config import HotkeyConfig

if sys.platform == "win32":
    import ctypes

    _user32 = ctypes.windll.user32

LLKHF_INJECTED = 0x10
VK_CAPITAL = 0x14
KEYEVENTF_KEYUP = 0x0002

MIN_HOLD_S = 0.0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

_VK_BY_NAME = {
    "escape": 0x1B, "tab": 0x09, "caps_lock": 0x14, "space": 0x20,
    "enter": 0x0D, "return": 0x0D, "backspace": 0x08, "delete": 0x2E,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "page_up": 0x21,
    "page_down": 0x22, "scroll_lock": 0x91, "num_lock": 0x90,
    "print_screen": 0x2C, "menu": 0x5D,
    "shift_l": 0xA0, "shift_r": 0xA1, "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "alt_l": 0xA4, "alt_r": 0xA5, "cmd": 0x5B, "cmd_r": 0x5C,
}
_VK_BY_NAME.update({f"f{i}": 0x70 + i - 1 for i in range(1, 25)})


class PushToTalkStateMachine:
    """Tracks press/release transitions and filters accidental taps.

    Callbacks (all optional):
      on_start()           - hotkey pressed, recording should begin
      on_stop(duration_s)  - released; duration_s >= min duration
      on_tap(duration_s)   - released too fast, should be discarded
    """

    def __init__(
        self,
        config: HotkeyConfig,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[float], None] | None = None,
        on_tap: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        import time

        self._config = config
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_tap = on_tap
        self._clock = clock or time.monotonic
        self._pressed_at: float | None = None

    @property
    def is_pressed(self) -> bool:
        return self._pressed_at is not None

    def press(self) -> None:
        if self._pressed_at is not None:
            # A genuine hold keeps emitting repeat key-downs, so the gap
            # stays small. A huge gap means a key-up was missed (stuck
            # state) - reset and accept this press instead of wedging.
            if self._clock() - self._pressed_at > 10.0:
                self._pressed_at = None
            else:
                return
        self._pressed_at = self._clock()
        if self._on_start is not None:
            self._on_start()

    def release(self) -> None:
        if self._pressed_at is None:
            return
        duration = self._clock() - self._pressed_at
        self._pressed_at = None
        min_s = max(self._config.min_duration_ms / 1000.0, MIN_HOLD_S)
        if duration < min_s:
            if self._on_tap is not None:
                self._on_tap(duration)
            return
        if self._on_stop is not None:
            self._on_stop(duration)

    def reset(self) -> None:
        """Force back to idle (e.g. on error or shutdown)."""
        self._pressed_at = None


def _parse_key(name: str):
    """Map a config string like 'caps_lock' to a pynput key."""
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown hotkey key: {name!r}")


class GlobalHotkey:
    """Wires a global pynput key to a PushToTalkStateMachine.

    On Windows the configured key is suppressed via a low-level event
    filter so it does not leak into other applications (e.g. Caps Lock
    toggling during dictation). Suppression requires the key to map to
    a virtual-key code; otherwise events are still received but not
    suppressed.
    """

    def __init__(
        self,
        config: HotkeyConfig,
        on_start: Callable[[], None] | None,
        on_stop: Callable[[float], None] | None,
        on_tap: Callable[[float], None] | None = None,
    ) -> None:
        self._target_key = _parse_key(config.key)
        self._machine = PushToTalkStateMachine(config, on_start, on_stop, on_tap)
        self._vk_codes = self._resolve_vk_codes(self._target_key)
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()
        self.suppress_failed = False
        self._caps_before: bool | None = None

    @property
    def is_pressed(self) -> bool:
        return self._machine.is_pressed

    @staticmethod
    def _resolve_vk_codes(target) -> set[int]:  # noqa: ANN001
        codes: set[int] = set()
        name = getattr(target, "name", None)
        if name in _VK_BY_NAME:
            codes.add(_VK_BY_NAME[name])
        char = getattr(target, "char", None)
        if isinstance(char, str) and len(char) == 1:
            upper = char.upper()
            if ("A" <= upper <= "Z") or ("0" <= upper <= "9"):
                codes.add(ord(upper))
        return codes

    def _matches(self, key) -> bool:  # noqa: ANN001
        if key == self._target_key:
            return True
        if isinstance(key, keyboard.KeyCode) and isinstance(self._target_key, keyboard.KeyCode):
            return key == self._target_key
        if isinstance(self._target_key, keyboard.Key) and isinstance(key, keyboard.KeyCode):
            return False
        return False

    def _on_press(self, key) -> None:  # noqa: ANN001
        if key is None:
            return
        with self._lock:
            if self._matches(key):
                self._machine.press()

    def _on_release(self, key) -> None:  # noqa: ANN001
        if key is None:
            return
        with self._lock:
            if self._matches(key):
                self._machine.release()

    def _handle_raw(self, msg: int, vk: int) -> bool:
        """Feed a raw win32 event to the state machine.

        Returns True when the event belongs to the push-to-talk key and
        should be suppressed from other applications.
        """
        if vk not in self._vk_codes:
            return False
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self._caps_before = self._caps_toggled()
            with self._lock:
                self._machine.press()
            return True
        if msg in (WM_KEYUP, WM_SYSKEYUP):
            with self._lock:
                self._machine.release()
            self._restore_caps_if_needed()
            return True
        return False

    def _caps_toggled(self) -> bool | None:
        if sys.platform != "win32":
            return None
        return bool(_user32.GetKeyState(VK_CAPITAL) & 1)

    def _tap_caps(self) -> None:
        if sys.platform != "win32":
            return
        _user32.keybd_event(VK_CAPITAL, 0, 0, 0)
        _user32.keybd_event(VK_CAPITAL, 0, KEYEVENTF_KEYUP, 0)

    def _restore_caps_if_needed(self) -> None:
        """Undo OS-level Caps Lock toggles that leaked through suppression."""
        now = self._caps_toggled()
        if self._caps_before is not None and now is not None and now != self._caps_before:
            self._tap_caps()
            self._caps_before = now

    def _win32_event_filter(self, msg, data) -> None:  # noqa: ANN001
        # Never touch injected events (including our own corrective taps).
        if getattr(data, "flags", 0) & LLKHF_INJECTED:
            return
        should_suppress = self._handle_raw(msg, data.vkCode)
        if should_suppress and self._listener is not None:
            # Must NOT be wrapped in try/except: pynput signals suppression
            # by raising an internal exception that the hook needs to see.
            self._listener.suppress_event()

    def start(self) -> None:
        if self._listener is not None:
            raise RuntimeError("GlobalHotkey already running")
        kwargs: dict = {"on_press": self._on_press, "on_release": self._on_release}
        if sys.platform == "win32" and self._vk_codes:
            kwargs["win32_event_filter"] = self._win32_event_filter
            if not hasattr(keyboard.Listener, "suppress_event"):
                self.suppress_failed = True
        self._listener = keyboard.Listener(**kwargs)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        self._machine.reset()
        self._listener.stop()
        self._listener = None
