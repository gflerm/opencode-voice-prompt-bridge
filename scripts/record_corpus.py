"""Guided benchmark-corpus recorder.

Put one prompt per line in data/corpus/prompts.txt (lines starting with
'#' and blank lines are ignored). For each prompt the script shows the
text, waits for Enter, counts down, records --seconds of audio, then
saves promptNN.wav plus promptNN.txt (the reference transcript you will
dictate).

Usage:
  .venv\\Scripts\\python.exe scripts\\record_corpus.py --list
  .venv\\Scripts\\python.exe scripts\\record_corpus.py [--seconds 10] [--start N]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np

from audio import Recorder, save_wav
from config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record benchmark corpus prompts.")
    parser.add_argument("--prompts", default=None, help="path to prompts.txt (default: <corpus>/prompts.txt)")
    parser.add_argument("--dir", default=None, help="corpus directory (default from config)")
    parser.add_argument("--seconds", type=float, default=10.0, help="recording duration per prompt")
    parser.add_argument("--start", type=int, default=None, help="first prompt number (default: continue numbering)")
    parser.add_argument("--force", action="store_true", help="re-record prompts whose files already exist")
    parser.add_argument("--list", action="store_true", help="show parsed prompts and exit")
    return parser.parse_args()


def load_prompts(path: Path) -> list[str]:
    prompts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            prompts.append(stripped)
    return prompts


def next_index(corpus_dir: Path, start: int | None) -> int:
    if start is not None:
        return start
    highest = 0
    for wav in corpus_dir.glob("prompt*.wav"):
        match = re.fullmatch(r"prompt(\d+)\.wav", wav.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def record_one(recorder: Recorder, seconds: float, sample_rate: int) -> np.ndarray:
    input("  Press Enter to start recording...")
    for n in (3, 2, 1):
        print(f"  {n}... ", end="", flush=True)
        time.sleep(1)
    print("SPEAK NOW!")
    recorder.start()
    time.sleep(seconds)
    return recorder.stop()


def main() -> int:
    args = parse_args()
    config = load_config()
    corpus_dir = Path(args.dir) if args.dir else REPO_ROOT / config.benchmark.corpus_dir
    prompts_path = Path(args.prompts) if args.prompts else corpus_dir / "prompts.txt"

    if not prompts_path.exists():
        print(f"Missing {prompts_path}")
        print("Create it with one prompt per line, e.g.:")
        print("  Run the test suite and commit with a short message")
        return 1
    prompts = load_prompts(prompts_path)
    if not prompts:
        print(f"No prompts found in {prompts_path}")
        return 1

    index = next_index(corpus_dir, args.start)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    if args.list:
        print(f"{len(prompts)} prompt(s) from {prompts_path}, numbering starts at {index:02d}:")
        for offset, prompt in enumerate(prompts):
            print(f"  prompt{index + offset:02d}: {prompt}")
        return 0

    print(f"Corpus dir : {corpus_dir}")
    print(f"Duration   : {args.seconds:.0f}s per prompt")
    print(f"Device     : {config.audio.device}\n")

    recorder = Recorder(config.audio)
    recorded = skipped = 0
    for offset, prompt in enumerate(prompts):
        number = index + offset
        wav_path = corpus_dir / f"prompt{number:02d}.wav"
        txt_path = corpus_dir / f"prompt{number:02d}.txt"
        if wav_path.exists() and not args.force:
            print(f"[{number:02d}] already recorded, skipping (use --force to redo)")
            skipped += 1
            continue
        print(f"[{number:02d}/{index + len(prompts) - 1:02d}] {prompt}")

        audio = record_one(recorder, args.seconds, config.audio.sample_rate)
        duration = audio.size / config.audio.sample_rate
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        print(f"  captured {duration:.2f}s  peak={peak:.3f}  rms={rms:.3f}")

        if peak < 0.03:
            print("  TOO QUIET - discarded, will re-record this number on next run")
            continue
        if peak > 0.97:
            print("  CLIPPING - discarded, will re-record this number on next run")
            continue

        save_wav(wav_path, audio, config.audio.sample_rate)
        txt_path.write_text(prompt + "\n", encoding="utf-8")
        print(f"  saved {wav_path.name} + {txt_path.name}")
        recorded += 1
        print()

    print(f"Done: {recorded} new clip(s), {skipped} skipped.")
    print("Re-record specific numbers by deleting their .wav first, or use --force.")
    print("Benchmark with:")
    print("  .venv\\Scripts\\python.exe scripts\\benchmark_whisper.py small.en medium.en distil-large-v3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
