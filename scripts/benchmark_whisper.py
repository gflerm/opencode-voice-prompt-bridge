"""Whisper model benchmark over a local WAV corpus.

Usage:
  .venv\\Scripts\\python.exe scripts\\benchmark_whisper.py [models ...]

Corpus: put 16 kHz mono WAVs in data/corpus/ (record them with
scripts/test_mic.py data/corpus/promptNN.wav). If a file with the same
stem + '.txt' exists it is used as the reference transcript for a
corrected-word score; otherwise only latency is reported.
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np

from config import load_config
from transcriber import Transcriber

DEFAULT_MODELS = ["small.en", "medium.en", "distil-large-v3"]


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sr


def corrected_words(reference: str, hypothesis: str) -> tuple[int, int]:
    """Greedy word-level score: (words matching, total reference words)."""
    ref = reference.lower().split()
    hyp = hypothesis.lower().split()
    matches = sum(1 for w in ref if w in hyp)
    return matches, len(ref)


def main() -> int:
    config = load_config()
    corpus_dir = REPO_ROOT / config.benchmark.corpus_dir
    wavs = sorted(corpus_dir.glob("*.wav"))
    if not wavs:
        print(f"No WAV files in {corpus_dir}")
        print("Record some first:  scripts\\test_mic.py data\\corpus\\prompt01.wav")
        return 1
    print(f"Corpus: {len(wavs)} file(s) from {corpus_dir}\n")

    models = sys.argv[1:] or DEFAULT_MODELS
    results: dict[str, list[float]] = {}
    for model_name in models:
        print(f"=== {model_name} ===")
        cfg = type(config.whisper)(**{**config.whisper.__dict__, "model": model_name})
        transcriber = Transcriber(cfg)
        try:
            transcriber.load()
        except Exception as exc:
            print(f"  load FAILED: {exc}\n")
            continue
        print(f"  device={transcriber.device} compute={transcriber.compute_type}")
        latencies: list[float] = []
        ratios: list[float] = []
        for wav_path in wavs:
            audio, sr = load_wav(wav_path)
            result = transcriber.transcribe(audio, sr)
            latencies.append(result.inference_s)
            ref_path = wav_path.with_suffix(".txt")
            line = f"  {wav_path.name}: {result.inference_s:5.2f}s  '{result.text}'"
            if ref_path.exists():
                matches, total = corrected_words(ref_path.read_text(encoding="utf-8"), result.text)
                ratio = matches / total if total else 0.0
                ratios.append(ratio)
                line += f"  [{matches}/{total}]"
            print(line)
        results[model_name] = latencies + ratios
        med = sorted(latencies)[len(latencies) // 2]
        summary = f"  median latency: {med:.2f}s"
        if ratios:
            summary += f"  mean word score: {sum(ratios) / len(ratios):.0%}"
        print(summary + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
