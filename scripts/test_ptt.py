"""Console push-to-talk: hold caps_lock, speak, release -> transcript printed.

Usage:
  .venv\\Scripts\\python.exe scripts\\test_ptt.py
Quit with Ctrl+C.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from audio import Recorder
from config import load_config
from hotkeys import GlobalHotkey
from transcriber import Transcriber


def main() -> int:
    config = load_config()
    recorder = Recorder(config.audio)
    transcriber = Transcriber(config.whisper)

    print(f"Loading {config.whisper.model}...")
    transcriber.load()
    print(f"Model ready on {transcriber.device}/{transcriber.compute_type}")

    def on_start() -> None:
        try:
            recorder.start()
            print("[rec] recording... (release to transcribe)")
        except Exception as exc:
            print(f"[rec] FAILED to start: {exc}")

    def on_stop(duration_s: float) -> None:
        try:
            audio = recorder.stop()
            if audio.size == 0:
                print("[transcribe] nothing captured")
                return
            result = transcriber.transcribe(audio, config.audio.sample_rate)
            print(f"\n  hold {duration_s:.1f}s | {result.inference_s:.2f}s to transcribe | {result.device}")
            print(f"  TEXT: {result.text or '(nothing recognized)'}\n")
        except Exception as exc:
            print(f"[transcribe] error: {exc}")

    def on_tap(duration_s: float) -> None:
        print(f"[tap {duration_s * 1000:.0f}ms - ignored, hold longer to record]")

    hotkey = GlobalHotkey(config.hotkey, on_start, on_stop, on_tap)
    hotkey.start()
    print(f"Push-to-talk: hold {config.hotkey.key.upper()} and speak. Ctrl+C to quit.\n")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        hotkey.stop()
        print("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
