"""Manual mic test: record until Enter, then report stats.

Usage: .venv\\Scripts\\python.exe scripts\\test_mic.py [output.wav]
Privacy: audio only stays in memory unless you pass an output path.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np

from audio import Recorder, list_input_devices
from config import load_config


def save_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def main() -> int:
    config = load_config()
    print("Input devices:")
    for idx, name in list_input_devices():
        marker = " <= configured" if idx == config.audio.device else ""
        print(f"  [{idx}] {name}{marker}")

    recorder = Recorder(config.audio)
    input("\nPress Enter to START recording...")
    recorder.start()
    input("Recording... press Enter to STOP")
    audio = recorder.stop()

    duration = audio.size / config.audio.sample_rate
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    print(f"\nCaptured {duration:.2f}s  peak={peak:.3f}")
    if peak < 0.01:
        print("WARNING: near-silence captured - check the configured device index")
        return 1

    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
        out.parent.mkdir(parents=True, exist_ok=True)
        save_wav(out, audio, config.audio.sample_rate)
        print(f"Saved: {out}")
    else:
        print("(not saved - pass a .wav path to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
