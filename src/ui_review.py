"""Editable review window: Enter sends, Esc cancels (FR-03).

Shows the adapted transcript; keeps the raw Whisper output so confirmed
edits can be learned as correction pairs (FR-05). Docks to a configured
screen corner.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Callable

from adaptation import diff_pairs
from transcriber import Transcript


@dataclass(frozen=True)
class ReviewPayload:
    text: str  # adapted text shown for editing
    original: str  # raw whisper output, used for learning diffs
    status: str = ""


@dataclass
class ReviewCallbacks:
    on_send: Callable[[str, list], None]
    on_cancel: Callable[[str], None]


class ReviewWindow:
    """One Toplevel per transcription. Not reusable after close."""

    def __init__(
        self,
        root: tk.Misc,
        payload: ReviewPayload,
        callbacks: ReviewCallbacks,
        anchor: str = "bottom_right",
        margin: int = 48,
    ) -> None:
        self._callbacks = callbacks
        self._payload = payload
        self._closed = False

        self.win = tk.Toplevel(root)
        self.win.title("Voice Prompt - review")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.geometry("720x220")

        self.status = tk.Label(
            self.win,
            text=payload.status or "review and edit before sending",
            anchor="w",
            fg="#555",
        )
        self.status.pack(fill="x", padx=8, pady=(6, 2))

        self.text = tk.Text(self.win, wrap="word", font=("Consolas", 11), height=6)
        self.text.pack(fill="both", expand=True, padx=8, pady=4)
        self.text.insert("1.0", payload.text)
        self.text.mark_set("insert", "end")
        self.text.focus_set()

        buttons = tk.Frame(self.win)
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        self.learn_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            buttons, text="Learn corrections", variable=self.learn_var
        ).pack(side="left")
        tk.Button(buttons, text="Send (Enter)", width=14, command=self.send).pack(side="right")
        tk.Button(buttons, text="Cancel (Esc)", width=14, command=self.cancel).pack(side="right", padx=(0, 6))

        self.win.bind("<Return>", lambda _e: self.send())
        self.win.bind("<Escape>", lambda _e: self.cancel())
        self.win.bind("<Control-Return>", self._newline)
        self.text.bind("<Return>", self._on_return)

        self._dock(anchor, margin)
        self.win.lift()
        self.win.focus_force()

    def _on_return(self, _event) -> str:
        self.send()
        return "break"

    def _dock(self, anchor: str, margin: int) -> None:
        self.win.update_idletasks()
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        w = self.win.winfo_width() or 720
        h = self.win.winfo_height() or 220
        if anchor == "center":
            x = (screen_w - w) // 2
            y = (screen_h - h) // 2
        else:
            x = margin if "left" in anchor else screen_w - w - margin
            y = margin if "top" in anchor else screen_h - h - margin - 60
        self.win.geometry(f"+{max(0, x)}+{max(0, y)}")

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
        pairs = diff_pairs(self._payload.original, text) if self.learn_var.get() else []
        self._busy("sending..." + (f" (learning {len(pairs)} correction(s))" if pairs else ""))
        self._callbacks.on_send(text, pairs)

    def cancel(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.win.destroy()
        self._callbacks.on_cancel(self.current_text())

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
        on_send: Callable[[str, list], None],
        window_factory: Callable[..., ReviewWindow] | None = None,
        placement: dict | None = None,
    ) -> None:
        self._root = root
        self._on_send = on_send
        self._factory = window_factory or ReviewWindow
        self._placement = placement or {}
        self._window: ReviewWindow | None = None
        self._pending: list[ReviewPayload] = []

    @property
    def is_open(self) -> bool:
        return self._window is not None and not self._window.closed

    def present(self, payload: ReviewPayload) -> None:
        if self.is_open:
            self._pending.append(payload)
            self._window.status.config(text="new dictation queued - finish this one first", fg="#555")
            return
        self._open(payload)

    def _open(self, payload: ReviewPayload) -> None:
        self._window = self._factory(
            self._root,
            payload,
            ReviewCallbacks(on_send=self._handle_send, on_cancel=self._handle_close),
            **self._placement,
        )

    def _handle_send(self, text: str, pairs: list) -> None:
        self._on_send(text, pairs)

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
