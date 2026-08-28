---
title: OpenCode Voice Prompt Bridge
description: Push-to-talk Whisper dictation for OpenCode on Windows - local transcription, tray control, login autostart.
status: active
priority: high
startDate: "2026-08-28"
tags: [voice, whisper, opencode, windows, python]
goals:
  - title: "Phases 0-1: capture, transcribe, review, deliver (PTT)"
    done: true
  - title: "Phase 2: adaptation engine (corrections, glossary, bypass)"
    done: true
  - title: "Native mode: bridge server + companion plugin delivery"
    done: true
  - title: "Phase 3: tray icon with toggles + login autostart"
    done: true
  - title: "Multilingual: large-v3 with per-utterance EN/AF auto-detect"
    done: true
  - title: "Publish to GitHub"
    done: true
  - title: "Reliability: single-instance guard + epoch event ids (restart-proof delivery)"
    done: true
  - title: "Spec section 14 reliability soak (100 cycles)"
    done: false
reminders:
  - due: "2026-09-15"
    note: "Review Afrikaans accuracy after a week of real use"
    done: false
timeline:
  - title: "Phases 0-2 + native bridge built and working"
    date: "2026-08-28"
    done: true
  - title: "Tray icon, binding toggle, autostart installer"
    date: "2026-08-28"
    done: true
  - title: "Single-instance guard fixed intermittent delivery"
    date: "2026-08-28"
    done: true
  - title: "Root cause closed: epoch event ids make app restarts invisible to the plugin"
    date: "2026-08-28"
    done: true
  - title: "Published to GitHub (MIT)"
    date: "2026-08-28"
    done: true
---

# OpenCode Voice Prompt Bridge

Push-to-talk voice dictation for [OpenCode](https://opencode.ai) on Windows.
Hold Caps Lock, speak, and your words land in the OpenCode prompt -
transcribed locally by Whisper, adapted by your personal vocabulary,
reviewed (or sent directly), with English and Afrikaans auto-detected
per utterance.

Everything runs locally: audio, transcription, adaptation. No cloud
services, no prompt text persisted (raw audio is never written to disk).

## Features

- **Push-to-talk** - global Caps Lock hotkey (configurable), suppressed
  so it never toggles Caps Lock in other apps
- **faster-whisper transcription** - CUDA (float16) or CPU, models from
  `small.en` to `large-v3`; `language = "auto"` detects each utterance's
  language (English/Afrikaans tested)
- **Native OpenCode delivery** - a companion plugin appends the
  transcript straight into the live OpenCode TUI prompt (no synthetic
  keystrokes), with a review window as fallback so text is never lost
- **Focused-window mode** - uncheck "Bound to OpenCode" in the tray to
  dictate into any app (typed or pasted, optional auto-Enter)
- **System tray icon** - live status tooltip, hotkey on/off toggle,
  OpenCode binding toggle, clean Quit
- **Login autostart** - windowless via `pythonw.exe` (HKCU Run key),
  logs to `data/app.log`
- **Adaptation engine** - learned correction pairs (from review-window
  edits), glossary aliases seeded into the Whisper initial prompt,
  context-sensitive rules, emergency bypass (F9)
- **Review window** - editable transcript before sending; "Learn
  corrections" turns your edits into reusable rules

## Requirements

- Windows 10/11
- Python 3.12+ (tested on 3.14 x64)
- A microphone
- NVIDIA GPU optional (CUDA paths auto-detected; CPU works via int8)

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.example.toml config.toml   # then edit to taste
```

CUDA note: `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` in
requirements.txt provide the DLLs for the GPU path; on CPU-only
machines you can remove them.

Run it:

```powershell
.venv\Scripts\python.exe src\app.py
```

Or windowless (tray icon only, logs to `data/app.log`):

```powershell
.venv\Scripts\pythonw.exe src\app.py
```

### OpenCode integration (native mode)

1. Install the companion plugin once:
   `.venv\Scripts\python.exe scripts\install_plugin.py`
2. Restart OpenCode (plugins load at startup).
3. Set `[opencode] mode = "native"` in `config.toml`.

Dictations are appended into the TUI prompt; review there and press
Enter. If the plugin does not pick a transcript up within 6 seconds,
the review window opens with the text instead - nothing is lost.

### Login autostart

```powershell
.venv\Scripts\python.exe scripts\install_autostart.py          # install
.venv\Scripts\python.exe scripts\install_autostart.py --status  # inspect
.venv\Scripts\python.exe scripts\install_autostart.py --remove  # remove
```

## Usage

| Action | How |
| --- | --- |
| Dictate | hold **Caps Lock**, speak, release |
| Cancel a review | **Esc** in the review window |
| Skip learned corrections once | tap **F9** |
| Toggle hotkey / OpenCode binding / quit | tray icon menu |
| Manage glossary and corrections | `scripts\vocab_manager.py` |

Configuration lives in `config.toml` (see `config.example.toml` for
every option: hotkey, audio device/gain, whisper model/language,
delivery mode, review-window placement, adaptation).

## Project layout

```
src/app.py            application bootstrap and event loop
src/audio.py          microphone capture (sounddevice)
src/transcriber.py    faster-whisper wrapper (CUDA/CPU auto)
src/hotkeys.py        global push-to-talk state machine (pynput)
src/adaptation.py     corrections, glossary aliases, context rules
src/storage.py        SQLite persistence (corrections, glossary, sessions)
src/ui_review.py      review window + learning flow (tkinter)
src/tray.py           system tray icon (pystray)
src/bridge_server.py  local HTTP state server the plugin polls
src/adapters/         delivery adapters (TUI keystrokes/paste, opencode CLI)
scripts/              installers, benchmarks, mic tools, vocab manager
tests/                unit tests (pytest)
docs/                 project spec and backlog
```

## Privacy

- Raw audio is held in memory only; nothing is written to disk.
- Prompt text is not stored; only metadata (latency, model, accepted)
  is recorded locally when `[adaptation] record_sessions = true`.
- All network traffic stays on `127.0.0.1` (OpenCode plugin bridge).

## Development

```powershell
.venv\Scripts\python.exe -m pytest tests
```

See `docs/OpenCode_Voice_Prompt_Bridge_PROJECT.md` for the original
spec and `docs/BACKLOG.md` for open ideas.
