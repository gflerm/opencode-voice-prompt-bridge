"""Microphone device discovery and push-to-talk PCM recorder."""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

from config import AudioConfig


def list_input_devices() -> list[tuple[int, str]]:
    """Return (index, name) pairs for all input-capable devices."""
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if int(dev["max_input_channels"]) > 0:
            devices.append((idx, str(dev["name"])))
    return devices


class Recorder:
    """Captures mono PCM from the microphone between start() and stop().

    Audio is accumulated as float32 samples and returned as a 1-D
    numpy array at the configured sample rate. Nothing is written to
    disk (privacy: no raw audio persisted by default).
    """

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._samples_captured = 0

    @property
    def samples_captured(self) -> int:
        return self._samples_captured

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            print(f"[audio] stream status: {status}")
        with self._lock:
            self._frames.append(indata.copy())
            self._samples_captured += frames

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recorder already running")
        with self._lock:
            self._frames = []
            self._samples_captured = 0
        self._stream = sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            device=self._config.device,
            dtype="float32",
            blocksize=max(1, self._config.sample_rate * self._config.block_ms // 1000),
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop capture and return the recorded audio (n_samples,) float32."""
        if self._stream is None:
            raise RuntimeError("Recorder not running")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0)
        return audio.mean(axis=1, dtype=np.float32) if audio.shape[1] > 1 else audio[:, 0]

    @staticmethod
    def trim_silence(audio: np.ndarray, threshold: float = 0.005, keep_ms: int = 150, sr: int = 16000) -> np.ndarray:
        """Trim leading/trailing near-silence, keeping a small pad."""
        if audio.size == 0:
            return audio
        loud = np.flatnonzero(np.abs(audio) > threshold)
        if loud.size == 0:
            return audio
        pad = sr * keep_ms // 1000
        start = max(0, int(loud[0]) - pad)
        end = min(audio.size, int(loud[-1]) + pad)
        return audio[start:end]
