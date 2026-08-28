"""VoiceTray tests with a stubbed pystray module (no real tray icon)."""

from pathlib import Path
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config import UiConfig
from tray import TOOLTIP_BASE, VoiceTray, draw_icon


class StubItem:
    def __init__(self, text, action=None, enabled=True, checked=None):
        self.text = text
        self.action = action
        self.enabled = enabled
        self.checked = checked


class StubMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


class StubIcon:
    def __init__(self, name, icon, tooltip, menu):
        self.name = name
        self.icon = icon
        self.tooltip = tooltip
        self.menu = menu
        self.run_detached_called = False
        self.stopped = False

    def run_detached(self):
        self.run_detached_called = True

    def stop(self):
        self.stopped = True


def make_stub():
    return SimpleNamespace(Item=StubItem, Menu=StubMenu, Icon=StubIcon)


def make_tray(toggles=None):
    tray = VoiceTray(module=make_stub(), toggles=toggles)
    tray.start()
    return tray


def items_of(tray):
    return [i for i in tray._icon.menu.items if isinstance(i, StubItem)]


def labels_of(tray):
    return [i.text for i in items_of(tray)]


def test_start_builds_menu_and_runs_detached():
    tray = make_tray()
    assert tray._icon.run_detached_called
    assert tray._icon.name == "opencode_voice_bridge"
    assert tray._icon.tooltip == TOOLTIP_BASE
    assert "Quit" in labels_of(tray)
    tray.stop()
    assert tray._icon is None


def test_toggles_render_in_order():
    state = {"hotkey": True, "bound": False}
    tray = make_tray(
        toggles=[
            ("Hotkey active", lambda: state["hotkey"], lambda v: state.__setitem__("hotkey", v)),
            (
                "Bound to OpenCode",
                lambda: state["bound"],
                lambda v: state.__setitem__("bound", v),
            ),
        ]
    )
    assert labels_of(tray)[1:] == ["Hotkey active", "Bound to OpenCode", "Quit"]


def test_toggle_action_flips_state():
    state = {"hotkey": True}
    tray = make_tray(
        toggles=[
            ("Hotkey active", lambda: state["hotkey"], lambda v: state.__setitem__("hotkey", v))
        ]
    )
    item = next(i for i in items_of(tray) if i.text == "Hotkey active")
    item.action()
    assert state["hotkey"] is False
    item.action()
    assert state["hotkey"] is True


def test_quit_flag_set_by_menu():
    tray = make_tray()
    quit_item = next(i for i in items_of(tray) if i.text == "Quit")
    assert not tray.request_quit
    quit_item.action()
    assert tray.request_quit


def test_status_buffers_before_start_and_updates_after():
    tray = VoiceTray(module=make_stub())
    tray.set_status("recording")
    tray.start()
    assert tray._icon.tooltip == f"{TOOLTIP_BASE} - recording"
    tray.set_status("idle")
    assert tray._icon.tooltip == f"{TOOLTIP_BASE} - idle"


def test_draw_icon_renders_mic_glyph():
    img = draw_icon()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0
    assert img.getpixel((32, 32))[3] == 255


def test_ui_tray_icon_default_enabled():
    assert UiConfig().tray_icon is True
