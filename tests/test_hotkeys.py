"""Push-to-talk state machine tests (no real keyboard needed)."""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config import HotkeyConfig, load_config
from hotkeys import (
    WM_KEYDOWN,
    WM_KEYUP,
    LLKHF_INJECTED,
    PushToTalkStateMachine,
)
from hotkeys import GlobalHotkey


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_machine(clock, events):
    return PushToTalkStateMachine(
        HotkeyConfig(min_duration_ms=200),
        on_start=lambda: events.append("start"),
        on_stop=lambda d: events.append(("stop", round(d, 3))),
        on_tap=lambda d: events.append(("tap", round(d, 3))),
        clock=clock,
    )


def test_press_starts_and_release_fires_stop():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.press()
    assert events == ["start"]
    clock.advance(1.5)
    m.release()

    assert events == ["start", ("stop", 1.5)]
    assert not m.is_pressed


def test_short_tap_is_filtered():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.press()
    clock.advance(0.05)
    m.release()

    assert events == ["start", ("tap", 0.05)]


def test_boundary_duration_uses_min_threshold():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.press()
    clock.advance(0.19)
    m.release()
    m.press()
    clock.advance(0.21)
    m.release()

    assert events == ["start", ("tap", 0.19), "start", ("stop", 0.21)]


def test_repeated_press_ignored_while_held():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.press()
    m.press()
    clock.advance(0.5)
    m.release()
    m.release()

    assert events == ["start", ("stop", 0.5)]


def test_release_without_press_is_noop():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.release()

    assert events == []


def test_reset_forces_idle():
    clock, events = FakeClock(), []
    m = make_machine(clock, events)

    m.press()
    m.reset()
    assert not m.is_pressed
    clock.advance(1.0)
    m.release()
    assert events == ["start"]


def test_load_config_defaults_and_roundtrip(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.hotkey.key == "caps_lock"
    assert cfg.audio.sample_rate == 16000
    assert cfg.whisper.model == "small.en"

    toml = tmp_path / "config.toml"
    toml.write_text(
        '[hotkey]\nkey = "f9"\nmin_duration_ms = 300\n'
        "[audio]\ndevice = 5\nsample_rate = 48000\n"
        '[whisper]\nmodel = "medium.en"\n'
        '[opencode]\nmode = "tui"\ndirect_send = true\n'
        '[ui]\nanchor = "top_left"\n'
        '[adaptation]\nbypass_hotkey = "f10"\n',
        encoding="utf-8",
    )
    cfg = load_config(toml)
    assert cfg.hotkey.key == "f9"
    assert cfg.hotkey.min_duration_ms == 300
    assert cfg.audio.device == 5
    assert cfg.audio.sample_rate == 48000
    assert cfg.whisper.model == "medium.en"
    assert cfg.whisper.language == "en"
    assert cfg.opencode.mode == "tui"
    assert cfg.opencode.direct_send is True
    assert cfg.ui.anchor == "top_left"
    assert cfg.adaptation.bypass_hotkey == "f10"


@pytest.mark.parametrize(
    "audio_builder",
    [
        pytest.param(lambda: __import__("numpy").array([], dtype="float32"), id="empty"),
    ],
)
def test_trim_silence_edge(audio_builder):
    from audio import Recorder

    assert Recorder.trim_silence(audio_builder()).size == 0


def make_hotkey(events):
    return GlobalHotkey(
        HotkeyConfig(key="caps_lock", min_duration_ms=200),
        on_start=lambda: events.append("start"),
        on_stop=lambda d: events.append(("stop", round(d, 3))),
        on_tap=lambda d: events.append(("tap", round(d, 3))),
    )


def test_vk_codes_resolved_for_caps_lock():
    hk = make_hotkey([])
    assert hk._vk_codes == {0x14}


def test_handle_raw_drives_state_machine_and_requests_suppression():
    clock, events = FakeClock(), []
    hk = make_hotkey(events)
    hk._machine._clock = clock

    assert hk._handle_raw(WM_KEYDOWN, 0x14) is True
    assert events == ["start"]
    clock.advance(1.0)
    assert hk._handle_raw(WM_KEYUP, 0x14) is True
    assert events == ["start", ("stop", 1.0)]


def test_handle_raw_ignores_other_keys():
    events = []
    hk = make_hotkey(events)

    assert hk._handle_raw(WM_KEYDOWN, 0x41) is False
    assert hk._handle_raw(0x0000, 0x14) is False
    assert events == []


def test_handle_raw_suppresses_key_repeat_without_retrigger():
    clock, events = FakeClock(), []
    hk = make_hotkey(events)
    hk._machine._clock = clock

    hk._handle_raw(WM_KEYDOWN, 0x14)
    clock.advance(0.1)
    hk._handle_raw(WM_KEYDOWN, 0x14)
    clock.advance(0.1)
    hk._handle_raw(WM_KEYDOWN, 0x14)
    assert events == ["start"]
    clock.advance(0.5)
    hk._handle_raw(WM_KEYUP, 0x14)
    assert events[-1] == ("stop", 0.7)


class FakeKeyData:
    def __init__(self, vk_code: int, flags: int = 0) -> None:
        self.vkCode = vk_code
        self.flags = flags


def test_filter_ignores_injected_events():
    clock, events = FakeClock(), []
    hk = make_hotkey(events)
    hk._machine._clock = clock

    hk._win32_event_filter(WM_KEYDOWN, FakeKeyData(0x14, flags=LLKHF_INJECTED))
    assert events == []

    hk._win32_event_filter(WM_KEYDOWN, FakeKeyData(0x14))
    assert events == ["start"]


def test_filter_ignores_other_keys_and_unknown_messages():
    clock, events = FakeClock(), []
    hk = make_hotkey(events)
    hk._machine._clock = clock

    hk._win32_event_filter(WM_KEYDOWN, FakeKeyData(0x41))
    hk._win32_event_filter(0x0000, FakeKeyData(0x14))
    assert events == []


def test_caps_guard_restores_toggled_state(monkeypatch):
    events = []
    hk = make_hotkey(events)
    hk._machine._clock = FakeClock()
    state = {"toggle": False}
    taps: list[int] = []

    def tap():
        taps.append(1)
        state["toggle"] = not state["toggle"]

    monkeypatch.setattr(hk, "_caps_toggled", lambda: state["toggle"])
    monkeypatch.setattr(hk, "_tap_caps", tap)

    hk._handle_raw(WM_KEYDOWN, 0x14)
    state["toggle"] = True  # OS toggled despite (failed) suppression
    hk._handle_raw(WM_KEYUP, 0x14)

    assert taps == [1]
    assert state["toggle"] is False


def test_caps_guard_noop_when_state_unchanged(monkeypatch):
    events = []
    hk = make_hotkey(events)
    hk._machine._clock = FakeClock()
    state = {"toggle": False}
    taps: list[int] = []

    def tap():
        taps.append(1)
        state["toggle"] = not state["toggle"]

    monkeypatch.setattr(hk, "_caps_toggled", lambda: state["toggle"])
    monkeypatch.setattr(hk, "_tap_caps", tap)

    hk._handle_raw(WM_KEYDOWN, 0x14)
    hk._handle_raw(WM_KEYUP, 0x14)
    assert taps == []
