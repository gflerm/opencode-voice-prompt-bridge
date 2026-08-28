"""Editable review window: Enter sends, Esc cancels (FR-03)."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from transcriber import Transcript


@dataclass
class ReviewCallbacks:
    on_send: Callable[[str], None]
    on_cancel: Callable[[str], None]


class ReviewWindow:
    """One Toplevel per transcription. Not resusable after close."""

    def __init__(self, root: tk.Misc, transcript: Transcript, callbacks: ReviewCallbacks) -> None:
        self._callbacks = callbacks
        self._closed = False
        self.win = tk.Toplevel(root)
        self.win.title("Voice Prompt - review")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.geometry("720x220")

        strip = (
            f"{transcript.device}/{transcript.compute_type}   "
            f"audio {transcript.duration_s:.1f}s -> {transcript.inference_s:.2f}s   "
            f"conf {'ok' if transcript.confident else 'LOW'}"
        )
        self.status = tk.Label(self.win, text=strip, anchor="w", fg="#555")
        self.status.pack(fill="x", padx=8, pady=(6, 2))

        self.text = tk.Text(self.win, wrap="word", font=("Consolas", 11), height=6)
        self.text.pack(fill="both", expand=True, padx=8, pady=4)
        self.text.insert("1.0", transcript.text)
        self.text.mark_set("insert", "end")
        self.text.focus_set()

        buttons = tk.Frame(self.win)
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(buttons, text="Send (Enter)", width=14, command=self.send).pack(side="right")
        tk.Button(buttons, text="Cancel (Esc)", width=14, command=self.cancel).pack(side="right", padx=(0, 6))

        self.win.bind("<Return>", lambda _e: self.send())
        self.win.bind("<Escape>", lambda _e: self.cancel())
        self.win.bind("<Control-Return>", self._newline)

    def _newline(self, _event) -> str:  # noqa: ANN001
        self.text.insert("insert", "\n")
        return "break"

    @property
    def closed(self) -> bool:
        return self._closed

    def current_text(self) -> str:
        return self.text.get("1.0", "end").strip()

    def _busy(self, message: str) -> None:
        self.status.config(text=message, fg="#a60")
        self.text.config(state="disabled")

    def send(self) -> None:
        if self._closed:
            return
        text = self.current_text()
        if not text:
            self.status.config(text="nothing to send - edit or press Esc", fg="#a00")
            return
        self._busy("sending to OpenCode...")
        self._callbacks.on_send(text)

    def cancel(self) -> None:
        if self._closed:
            return
        text = self.current_text()
        self._closed = True
        self.win.destroy()
        self._callbacks.on_cancel(text)

    def finish_ok(self, detail: str) -> None:
        self._closed = True
        self.win.destroy()

    def finish_error(self, detail: str) -> None:
        self.text.config(state="normal")
        self.status.config(text=f"SEND FAILED: {detail}", fg="#a00")
        self.win.title("Voice Prompt - send failed (edit & retry, or Esc)")


class ReviewManager:
    """Shows one review window at a time; queues results arriving meanwhile."""

    def __init__(
        self,
        root: tk.Misc,
        on_send: Callable[[str], None],
        window_factory: Callable[..., ReviewWindow] | None = None,
    ) -> None:
        self._root = root
        self._on_send = on_send
        self._factory = window_factory or ReviewWindow
        self._window: ReviewWindow | None = None
        self._pending: list[Transcript] = []

    @property
    def is_open(self) -> bool:
        return self._window is not None and not self._window.closed

    def present(self, transcript: Transcript) -> None:
        if self.is_open:
            self._pending.append(transcript)
            self._window.status.config(text="new dictation queued - finish this one first", fg="#555")
            return
        self._open(transcript)

    def _open(self, transcript: Transcript) -> None:
        self._window = self._factory(
            self._root,
            transcript,
            ReviewCallbacks(on_send=self._handle_send, on_cancel=self._handle_close),
        )

    def _handle_send(self, text: str) -> None:
        self._on_send(text)

    def _handle_close(self, _text: str) -> None:
        self._window = None
        if self._pending:
            self._open(self._pending.pop(0))

    def send_succeeded(self) -> None:
        if self._window is not None:
            self._window.finish_ok("sent")
            self._handle_close("")

    def send_failed(self, detail: str) -> None:
        if self._window is not None:
            self._window.finish_error(detail)
