"""System tray icon: status tooltip, runtime toggles, graceful quit.

pystray owns its own thread, so the menu never touches tkinter: the
Quit item only sets a flag that App._poll_events checks on its regular
tick, keeping all shutdown work on the Tk main loop. Checkable toggle
items delegate their state to getter/setter callbacks supplied by the
app (label, is_checked() -> bool, set_value(bool)).
"""

from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw

TOOLTIP_BASE = "OpenCode Voice Bridge"

_ICON_SIZE = 64
_BG = (31, 41, 55, 255)
_FG = (248, 250, 252, 255)


def draw_icon() -> Image.Image:
    """Render a small microphone glyph so no binary asset is needed."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=_BG)
    d.rounded_rectangle((24, 12, 40, 34), radius=8, fill=_FG)
    d.arc((18, 22, 46, 40), start=0, end=180, fill=_FG, width=4)
    d.line((32, 39, 32, 47), fill=_FG, width=4)
    d.line((24, 49, 40, 49), fill=_FG, width=4)
    return img


class VoiceTray:
    """Detached tray icon with checkable toggles and a thread-safe quit flag.

    set_status() may be called from any thread (hotkey listener, Tk
    loop); updates before start() are buffered into the initial tooltip.
    """

    def __init__(
        self,
        module=None,  # noqa: ANN001 - injectable pystray stand-in for tests
        tooltip_base: str = TOOLTIP_BASE,
        toggles: list[tuple[str, Callable[[], bool], Callable[[bool], None]]] | None = None,
    ) -> None:
        self._pystray = module
        self._tooltip_base = tooltip_base
        self._status = ""
        self._quit = threading.Event()
        self._icon = None
        self._toggles = list(toggles or [])

    def _tooltip(self) -> str:
        return f"{self._tooltip_base} - {self._status}" if self._status else self._tooltip_base

    def start(self) -> None:
        import pystray

        pys = self._pystray or pystray
        items: list = [pys.MenuItem(self._tooltip(), action=None, enabled=False), pys.Menu.SEPARATOR]
        for index, toggle in enumerate(self._toggles):
            if index:
                items.append(pys.Menu.SEPARATOR)
            label, getter, setter = toggle
            items.append(
                pys.MenuItem(label, self._toggle_action(getter, setter), checked=lambda *args, g=getter: g())
            )
        items.append(pys.Menu.SEPARATOR)
        items.append(pys.MenuItem("Quit", self._on_quit))
        self._icon = pys.Icon("opencode_voice_bridge", draw_icon(), self._tooltip(), pys.Menu(*items))
        self._icon.run_detached()

    @staticmethod
    def _toggle_action(getter: Callable[[], bool], setter: Callable[[bool], None]) -> Callable:  # noqa: ANN001
        def action(*_args) -> None:
            setter(not getter())

        return action

    def _on_quit(self, icon=None, item=None) -> None:  # noqa: ANN001
        self._quit.set()

    @property
    def request_quit(self) -> bool:
        return self._quit.is_set()

    def set_status(self, text: str) -> None:
        self._status = text
        if self._icon is not None:
            try:
                self._icon.tooltip = self._tooltip()
            except Exception as exc:
                print(f"[tray] tooltip update failed: {exc}")

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            pass
        self._icon = None
