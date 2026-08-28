"""Manual mic test: record until Enter (or --seconds N), then report stats.

Usage:
  .venv\\Scripts\\python.exe scripts\\test_mic.py [output.wav]
  .venv\\Scripts\\python.exe scripts\\test_mic.py output.wav --seconds 10
Privacy: audio only stays in memory unless you pass an output path.
"""

from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np

from audio import Recorder, list_input_devices
from config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a test clip from the microphone.")
    parser.add_argument("output", nargs="?", help="optional .wav path to save the recording")
    parser.add_argument(
        "--seconds", type=float, default=None,
        help="record for a fixed duration instead of waiting for Enter",
    )
    return parser.parse_args()


def save_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def main() -> int:
    args = parse_args()
    config = load_config()
    print("Input devices:")
    for idx, name in list_input_devices():
        marker = " <= configured" if idx == config.audio.device else ""
        print(f"  [{idx}] {name}{marker}")

    recorder = Recorder(config.audio)
    if args.seconds is not None:
        print(f"\nRecording starts in 3... ", end="", flush=True)
        for n in (2, 1):
            time.sleep(1)
            print(f"{n}... ", end="", flush=True)
        time.sleep(1)
        print("SPEAK NOW!")
        recorder.start()
        time.sleep(args.seconds)
    else:
        input("\nPress Enter to START recording...")
        recorder.start()
        input("Recording... press Enter to STOP")
    audio = recorder.stop()

    duration = audio.size / config.audio.sample_rate
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    print(f"\nCaptured {duration:.2f}s  peak={peak:.3f}  rms={rms:.3f}")
    if peak < 0.01:
        print("WARNING: near-silence captured - check the configured device index")
        return 1

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        save_wav(out, audio, config.audio.sample_rate)
        print(f"Saved: {out}")
    else:
        print("(not saved - pass a .wav path to save)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
