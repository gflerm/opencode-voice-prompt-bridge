"""faster-whisper transcription wrapper with CUDA/CPU auto-detect."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

if sys.platform == "win32":
    _nvidia_bin = Path(__import__("sysconfig").get_paths()["purelib"]) / "nvidia"
    for _sub in ("cublas", "cudnn"):
        _d = _nvidia_bin / _sub / "bin"
        if _d.is_dir():
            os.add_dll_directory(str(_d))
            os.environ["PATH"] = str(_d) + os.pathsep + os.environ.get("PATH", "")

from faster_whisper import WhisperModel

from config import WhisperConfig


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    avg_logprob: float
    no_speech_prob: float
    duration_s: float
    inference_s: float
    device: str
    compute_type: str

    @property
    def confident(self) -> bool:
        return self.avg_logprob > -0.5 and self.no_speech_prob < 0.6


def _resolve_device(config: WhisperConfig) -> str:
    if config.device != "auto":
        return config.device
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def _resolve_compute_type(config: WhisperConfig, device: str) -> str:
    if config.compute_type != "auto":
        return config.compute_type
    return "float16" if device == "cuda" else "int8"


TARGET_SAMPLE_RATE = 16000


def resample_to_16k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Linear-interpolation resample to 16 kHz mono (good enough for spike)."""
    if sample_rate == TARGET_SAMPLE_RATE or audio.size == 0:
        return audio
    duration = audio.size / sample_rate
    target_len = int(round(duration * TARGET_SAMPLE_RATE))
    if target_len <= 1:
        return audio
    src_idx = np.arange(target_len, dtype=np.float64) * (sample_rate / TARGET_SAMPLE_RATE)
    src_idx = np.clip(src_idx, 0, audio.size - 1)
    return np.interp(src_idx, np.arange(audio.size), audio).astype(np.float32)


class Transcriber:
    """Loads a faster-whisper model once and transcribes float32 PCM arrays."""

    def __init__(self, config: WhisperConfig) -> None:
        self._config = config
        self._model: WhisperModel | None = None
        self.device: str | None = None
        self.compute_type: str | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        self.device = _resolve_device(self._config)
        self.compute_type = _resolve_compute_type(self._config, self.device)
        self._model = WhisperModel(
            self._config.model,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int = TARGET_SAMPLE_RATE) -> Transcript:
        """Transcribe mono float32 PCM in [-1, 1] (resampled to 16 kHz)."""
        if self._model is None:
            self.load()
        assert self._model is not None
        audio = resample_to_16k(audio, sample_rate)
        started = time.perf_counter()
        segments, info = self._model.transcribe(
            audio,
            language=self._config.language,
            beam_size=5,
            vad_filter=True,
        )
        parts: list[str] = []
        logprobs: list[float] = []
        no_speech: list[float] = []
        for segment in segments:
            parts.append(segment.text.strip())
            logprobs.append(segment.avg_logprob)
            no_speech.append(segment.no_speech_prob)
        text = " ".join(p for p in parts if p)
        return Transcript(
            text=text,
            language=info.language,
            avg_logprob=sum(logprobs) / len(logprobs) if logprobs else 0.0,
            no_speech_prob=max(no_speech) if no_speech else 0.0,
            duration_s=audio.size / sample_rate,
            inference_s=time.perf_counter() - started,
            device=self.device or "cpu",
            compute_type=self.compute_type or "int8",
        )
