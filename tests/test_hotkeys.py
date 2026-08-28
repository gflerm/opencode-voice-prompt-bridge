"""Push-to-talk state machine tests (no real keyboard needed)."""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from config import HotkeyConfig, load_config
from hotkeys import PushToTalkStateMachine


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
        '[whisper]\nmodel = "medium.en"\n',
        encoding="utf-8",
    )
    cfg = load_config(toml)
    assert cfg.hotkey.key == "f9"
    assert cfg.hotkey.min_duration_ms == 300
    assert cfg.audio.device == 5
    assert cfg.audio.sample_rate == 48000
    assert cfg.whisper.model == "medium.en"
    assert cfg.whisper.language == "en"


@pytest.mark.parametrize(
    "audio_builder",
    [
        pytest.param(lambda: __import__("numpy").array([], dtype="float32"), id="empty"),
    ],
)
def test_trim_silence_edge(audio_builder):
    from audio import Recorder

    assert Recorder.trim_silence(audio_builder()).size == 0
