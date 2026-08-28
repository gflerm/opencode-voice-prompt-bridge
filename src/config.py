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
class AppConfig:
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)


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
    )
