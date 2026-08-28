"""Re-record specific corpus clips in place (keeps existing .txt references).

Usage:
  .venv\\Scripts\\python.exe scripts\\rerecord_clips.py 5 16 18 20 24 [--seconds 10]

For each number the script shows the reference text, waits for Enter,
counts down, records, and overwrites promptNN.wav.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np

from audio import Recorder, save_wav
from config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-record corpus clips by number.")
    parser.add_argument("numbers", nargs="+", type=int, help="prompt numbers, e.g. 5 16 18")
    parser.add_argument("--seconds", type=float, default=10.0, help="recording duration per clip")
    parser.add_argument("--dir", default=None, help="corpus directory (default from config)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    corpus_dir = Path(args.dir) if args.dir else REPO_ROOT / config.benchmark.corpus_dir

    missing = [
        n for n in args.numbers
        if not (corpus_dir / f"prompt{n:02d}.txt").exists()
    ]
    if missing:
        print(f"No .txt reference for prompt(s): {', '.join(f'{n:02d}' for n in missing)}")
        return 1

    print(f"Corpus dir: {corpus_dir}   duration: {args.seconds:.0f}s per clip\n")
    recorder = Recorder(config.audio)
    for number in args.numbers:
        txt_path = corpus_dir / f"prompt{number:02d}.txt"
        wav_path = corpus_dir / f"prompt{number:02d}.wav"
        prompt = txt_path.read_text(encoding="utf-8").strip()
        print(f"--- prompt{number:02d} ---")
        print(f"    {prompt}")
        input("    Press Enter to arm... ")
        for n in (3, 2, 1):
            print(f"    {n}... ", end="", flush=True)
            time.sleep(1)
        print("SPEAK NOW!")
        recorder.start()
        time.sleep(args.seconds)
        audio = recorder.stop()

        duration = audio.size / config.audio.sample_rate
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        save_wav(wav_path, audio, config.audio.sample_rate)
        flag = ""
        if peak < 0.03:
            flag = "  << TOO QUIET, run this number again"
        elif peak > 0.97:
            flag = "  << CLIPPING, run this number again"
        print(f"    saved {wav_path.name}  {duration:.2f}s  peak={peak:.3f}  rms={rms:.3f}{flag}\n")

    print("Re-benchmark these with:")
    print("  .venv\\Scripts\\python.exe scripts\\benchmark_whisper.py medium.en")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
