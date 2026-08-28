"""Application bootstrap: push-to-talk -> transcription -> review -> OpenCode.

Run:  .venv\\Scripts\\python.exe src\\app.py
Quit: Ctrl+C in the console (or close the review window and Ctrl+C).
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from adapters import opencode as oc_adapter
from audio import Recorder
from config import load_config
from hotkeys import GlobalHotkey
from transcriber import Transcriber
from ui_review import ReviewManager

EVENT = "event"
UI_EVENT_TRANSCRIPT = "transcript"
UI_EVENT_SEND_OK = "send_ok"
UI_EVENT_SEND_FAIL = "send_fail"


class App:
    def __init__(self) -> None:
        self.config = load_config()
        self.recorder = Recorder(self.config.audio)
        self.transcriber = Transcriber(self.config.whisper)
        self.events: queue.Queue = queue.Queue()
        self.transcribe_jobs: queue.Queue = queue.Queue()

        print(f"Loading {self.config.whisper.model}...")
        self.transcriber.load()
        print(f"Model ready on {self.transcriber.device}/{self.transcriber.compute_type}")

        self.root = tk.Tk()
        self.root.withdraw()
        self.review = ReviewManager(self.root, on_send=self._dispatch_send)

        self.hotkey = GlobalHotkey(
            self.config.hotkey,
            on_start=self._on_record_start,
            on_stop=self._on_record_stop,
            on_tap=self._on_tap,
        )
        if self.hotkey.suppress_failed:
            print("WARNING: key suppression unavailable - hotkey may leak to other apps")

        self.worker = threading.Thread(target=self._transcribe_worker, daemon=True)
        self.worker.start()

    def _on_record_start(self) -> None:
        try:
            self.recorder.start()
            print("[rec] recording...")
        except Exception as exc:
            print(f"[rec] FAILED to start: {exc}")

    def _on_record_stop(self, duration_s: float) -> None:
        try:
            audio = self.recorder.stop()
        except Exception as exc:
            print(f"[rec] stop failed: {exc}")
            return
        if audio.size == 0:
            print("[app] empty capture - ignored")
            return
        self.transcribe_jobs.put(audio)
        print(f"[app] captured {duration_s:.1f}s, transcribing...")

    def _on_tap(self, duration_s: float) -> None:
        print(f"[tap {duration_s * 1000:.0f}ms - ignored]")

    def _transcribe_worker(self) -> None:
        while True:
            audio: np.ndarray = self.transcribe_jobs.get()
            if audio is None:
                return
            try:
                result = self.transcriber.transcribe(audio, self.config.audio.sample_rate)
                self.events.put((UI_EVENT_TRANSCRIPT, result))
            except Exception as exc:
                print(f"[transcribe] error: {exc}")

    def _dispatch_send(self, text: str) -> None:
        def job() -> None:
            try:
                oc_adapter.send(self.config.opencode, text)
                self.events.put((UI_EVENT_SEND_OK, text))
            except oc_adapter.AdapterError as exc:
                self.events.put((UI_EVENT_SEND_FAIL, str(exc)))

        threading.Thread(target=job, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == UI_EVENT_TRANSCRIPT:
                    print(f"[app] transcript ready ({payload.inference_s:.2f}s)")
                    self.review.present(payload)
                elif event == UI_EVENT_SEND_OK:
                    print("[app] sent to OpenCode")
                    self.review.send_succeeded()
                elif event == UI_EVENT_SEND_FAIL:
                    print(f"[app] send failed: {payload}")
                    self.review.send_failed(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_events)

    def run(self) -> int:
        self.hotkey.start()
        key = self.config.hotkey.key.upper()
        print(f"Push-to-talk: hold {key} and speak. Esc in review cancels. Ctrl+C quits.\n")
        self.root.after(80, self._poll_events)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.hotkey.stop()
            self.transcribe_jobs.put(None)
            print("stopped")
        return 0


def main() -> int:
    return App().run()


if __name__ == "__main__":
    raise SystemExit(main())
