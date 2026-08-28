"""TOML configuration loading with defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.toml"


@dataclass(frozen=True)
class HotkeyConfig:
    key: str = "caps_lock"
    min_duration_ms: int = 200


@dataclass(frozen=True)
class AudioConfig:
    device: int | None = 1
    sample_rate: int = 16000
    channels: int = 1
    block_ms: int = 30
    gain: float = 1.0


@dataclass(frozen=True)
class WhisperConfig:
    model: str = "small.en"
    device: str = "auto"
    compute_type: str = "auto"
    language: str = "en"


@dataclass(frozen=True)
class BenchmarkConfig:
    corpus_dir: str = "data/corpus"


@dataclass(frozen=True)
class OpencodeConfig:
    command: str = "opencode"
    mode: str = "run"  # "run" | "attach" | "tui" | "native"
    attach_server: str = ""
    show_console: bool = True
    keep_open: bool = True
    working_dir: str = ""
    # Native mode: local port the companion plugin polls for dictations.
    native_port: int = 8765
    # Opt-in only (spec section 18): skip the review window and send on
    # key release. On send failure the review window opens as fallback.
    direct_send: bool = False
    # TUI mode delivery:
    #   auto_enter true  = submit immediately after delivery (fast flow)
    #   auto_enter false = leave the text in the prompt to review and
    #                      press Enter yourself
    # input_method "paste" = clipboard paste (fast; TUI may show a chip)
    # input_method "type"  = unicode keystrokes, visible and editable
    #                       inline, clipboard untouched
    auto_enter: bool = True
    input_method: str = "paste"


@dataclass(frozen=True)
class UiConfig:
    # Where the review window docks: bottom_right | bottom_left | top_right | top_left | center
    anchor: str = "bottom_right"
    margin: int = 48


@dataclass(frozen=True)
class AdaptationConfig:
    db_path: str = "data/adaptation.db"
    bypass_hotkey: str = "f9"
    record_sessions: bool = True
    initial_prompt_terms: int = 20


@dataclass(frozen=True)
class AppConfig:
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    opencode: OpencodeConfig = field(default_factory=OpencodeConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    adaptation: AdaptationConfig = field(default_factory=AdaptationConfig)


def _build(cls, data: dict):  # noqa: ANN001 - small internal helper
    valid = set(cls.__dataclass_fields__)
    return cls(**{k: v for k, v in data.items() if k in valid})


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load config.toml if present; otherwise return defaults."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    return AppConfig(
        hotkey=_build(HotkeyConfig, raw.get("hotkey", {})),
        audio=_build(AudioConfig, raw.get("audio", {})),
        whisper=_build(WhisperConfig, raw.get("whisper", {})),
        benchmark=_build(BenchmarkConfig, raw.get("benchmark", {})),
        opencode=_build(OpencodeConfig, raw.get("opencode", {})),
        ui=_build(UiConfig, raw.get("ui", {})),
        adaptation=_build(AdaptationConfig, raw.get("adaptation", {})),
    )
