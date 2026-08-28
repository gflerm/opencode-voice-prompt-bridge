"""Application bootstrap: push-to-talk -> transcription -> adaptation -> review -> target.

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
from adapters import tui as tui_adapter
from adaptation import AdaptationEngine
from audio import Recorder
from config import REPO_ROOT, load_config
from hotkeys import GlobalHotkey
from storage import AdaptationStore, seed_glossary
from transcriber import Transcriber
from ui_review import ReviewManager, ReviewPayload

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
        self.target_hwnd = 0
        self.last_inference_s = 0.0
        self.last_payload: ReviewPayload | None = None

        db_path = Path(self.config.adaptation.db_path)
        if not db_path.is_absolute():
            db_path = REPO_ROOT / db_path
        self.store = AdaptationStore(db_path)
        seeded = seed_glossary(self.store)
        if seeded:
            print(f"[adapt] seeded glossary with {seeded} terms")
        self.engine = AdaptationEngine(self.store)

        print(f"Loading {self.config.whisper.model}...")
        self.transcriber.load()
        print(f"Model ready on {self.transcriber.device}/{self.transcriber.compute_type}")

        self.root = tk.Tk()
        self.root.withdraw()
        self.review = ReviewManager(
            self.root,
            on_send=self._dispatch_send,
            placement=dict(anchor=self.config.ui.anchor, margin=self.config.ui.margin),
        )

        self.hotkey = GlobalHotkey(
            self.config.hotkey,
            on_start=self._on_record_start,
            on_stop=self._on_record_stop,
            on_tap=self._on_tap,
        )

        self.bypass_hotkey = GlobalHotkey(
            type(self.config.hotkey)(key=self.config.adaptation.bypass_hotkey, min_duration_ms=100),
            on_start=self._on_bypass,
            on_stop=None,
            on_tap=None,
        )

        self.worker = threading.Thread(target=self._transcribe_worker, daemon=True)
        self.worker.start()

    def _on_record_start(self) -> None:
        self.target_hwnd = tui_adapter.capture_foreground()
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

    def _on_bypass(self) -> None:
        self.engine.bypass_next = True
        print(f"[adapt] {self.config.adaptation.bypass_hotkey.upper()}: learned corrections bypassed for next utterance")

    def _transcribe_worker(self) -> None:
        while True:
            audio: np.ndarray = self.transcribe_jobs.get()
            if audio is None:
                return
            try:
                result = self.transcriber.transcribe(
                    audio,
                    self.config.audio.sample_rate,
                    initial_prompt=self.engine.glossary_initial_prompt(self.config.adaptation.initial_prompt_terms),
                )
                adapted = self.engine.apply(result.text)
                payload = ReviewPayload(
                    text=adapted,
                    original=result.text,
                    status=(
                        f"{result.device}/{result.compute_type}   "
                        f"audio {result.duration_s:.1f}s -> {result.inference_s:.2f}s   "
                        f"conf {'ok' if result.confident else 'LOW'}"
                    ),
                )
                self.events.put((UI_EVENT_TRANSCRIPT, (result, payload)))
            except Exception as exc:
                print(f"[transcribe] error: {exc}")

    def _dispatch_send(self, text: str, pairs: list) -> None:
        def job() -> None:
            try:
                if pairs:
                    learned = self.engine.learn_pairs(pairs)
                    if learned:
                        print(f"[adapt] learned {learned} correction(s)")
                if self.config.opencode.mode == "tui":
                    tui_adapter.send_to_window(
                        self.target_hwnd,
                        text,
                        press_enter=self.config.opencode.auto_enter,
                        input_method=self.config.opencode.input_method,
                    )
                else:
                    oc_adapter.send(self.config.opencode, text)
                self.events.put((UI_EVENT_SEND_OK, text))
                if self.config.adaptation.record_sessions:
                    self.store.record_session(
                        int(self.last_inference_s * 1000), self.config.whisper.model, True
                    )
            except Exception as exc:
                self.events.put((UI_EVENT_SEND_FAIL, str(exc)))

        threading.Thread(target=job, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == UI_EVENT_TRANSCRIPT:
                    result, review_payload = payload
                    self.last_payload = review_payload
                    self.last_inference_s = result.inference_s
                    note = " (adapted)" if review_payload.text != review_payload.original else ""
                    print(f"[app] transcript ready ({result.inference_s:.2f}s){note}")
                    if self.config.opencode.direct_send:
                        print("[direct] sending straight to target (review skipped)")
                        self._dispatch_send(review_payload.text, [])
                    else:
                        self.review.present(review_payload)
                elif event == UI_EVENT_SEND_OK:
                    print("[app] sent")
                    self.review.send_succeeded()
                elif event == UI_EVENT_SEND_FAIL:
                    print(f"[app] send failed: {payload}")
                    if self.config.opencode.direct_send and self.last_payload is not None:
                        print("[app] opening review window so the text is not lost")
                        self.review.present(self.last_payload)
                    self.review.send_failed(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_events)

    def run(self) -> int:
        self.hotkey.start()
        self.bypass_hotkey.start()
        if self.hotkey.suppress_failed:
            print("WARNING: key suppression unavailable - hotkey may leak to other apps")
        key = self.config.hotkey.key.upper()
        mode = self.config.opencode.mode
        if mode == "tui":
            target_note = "text will be pasted into the window focused when you start recording"
        else:
            target_note = f"prompts spawn: {self.config.opencode.command} {self.config.opencode.mode}"
        print(f"Push-to-talk: hold {key} and speak. Esc in review cancels. Ctrl+C quits.")
        print(f"Bypass: tap {self.config.adaptation.bypass_hotkey.upper()} to skip learned corrections once.")
        print(f"Target ({mode}): {target_note}\n")
        self.root.after(80, self._poll_events)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.hotkey.stop()
            self.bypass_hotkey.stop()
            self.transcribe_jobs.put(None)
            self.store.close()
            print("stopped")
        return 0


def main() -> int:
    return App().run()


if __name__ == "__main__":
    raise SystemExit(main())
