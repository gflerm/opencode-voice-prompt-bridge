"""Push-to-talk hotkey state machine + global pynput listener."""

from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard

from config import HotkeyConfig

MIN_HOLD_S = 0.0


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

    The configured key is suppressed while held so it does not leak
    into other applications (e.g. Caps Lock toggling during dictation).
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
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()

    @property
    def is_pressed(self) -> bool:
        return self._machine.is_pressed

    def _matches(self, key) -> bool:  # noqa: ANN001
        if key == self._target_key:
            return True
        normalized = self._target_key
        if isinstance(normalized, keyboard.Key) and isinstance(key, keyboard.KeyCode):
            return False
        if isinstance(key, keyboard.KeyCode) and isinstance(normalized, keyboard.KeyCode):
            return key == normalized
        # Key <-> KeyCode equivalences (e.g. ctrl variants) are left strict for v0.1
        return False

    def _on_press(self, key) -> bool:  # noqa: ANN001
        if key is None:
            return True
        with self._lock:
            if self._matches(key):
                self._machine.press()
                return False  # suppress the key globally
        return True

    def _on_release(self, key) -> bool:  # noqa: ANN001
        if key is None:
            return True
        with self._lock:
            if self._matches(key):
                self._machine.release()
                return False
        return True

    def start(self) -> None:
        if self._listener is not None:
            raise RuntimeError("GlobalHotkey already running")
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release, suppress=self._matches
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        self._machine.reset()
        self._listener.stop()
        self._listener = None
