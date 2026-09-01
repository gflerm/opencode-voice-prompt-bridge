# OpenCode Voice Prompt Bridge

**Version:** Draft v0.1  
**Date:** 27 August 2026  
**Platform:** Windows 11  
**Primary language:** Python 3.12 recommended

> **Status (2026-08-28): DONE.** v0.1 is built, tested (56 unit tests)
> and published at github.com/gflerm/opencode-voice-prompt-bridge.
> Shipped beyond this draft: native plugin delivery with restart-proof
> event ids, single-instance guard, self-healing hotkey state, system
> tray (hotkey + OpenCode-binding toggles), login autostart, English/
> Afrikaans auto-detect on multilingual models, English-only medium.en
> default. See README.md for the current user-facing documentation and
> BACKLOG.md for what was deliberately deferred.

## Purpose

Build a lightweight local voice-input layer for OpenCode CLI. Hold a configurable hotkey, speak, release, review/edit the transcript, and send the final prompt to OpenCode. No TTS is required.

## Core Design

1. Global push-to-talk hotkey starts/stops microphone capture.
2. Audio is captured as mono PCM/WAV, initially 16 kHz.
3. `faster-whisper` transcribes locally using CUDA when available, with CPU fallback.
4. An adaptation layer applies approved glossary terms and learned correction mappings.
5. A small editable review window opens.
6. **Enter** sends the prompt; **Esc** cancels.
7. Confirmed corrections can update the local vocabulary database.
8. The OpenCode integration is an adapter rather than terminal keystroke automation.

## Recommended Stack

- Python 3.12 x64 in a virtual environment.
- `faster-whisper` / CTranslate2 for STT.
- CUDA 12 + cuDNN 9 for current NVIDIA GPU acceleration.
- `sounddevice` + NumPy for microphone capture.
- `pynput` (or `keyboard`) for push-to-talk.
- Tkinter for the v0.1 review/settings UI.
- SQLite (`sqlite3`) for persistent correction and vocabulary data.
- TOML for configuration.
- `pytest` for tests.
- PyInstaller later for packaging.

## Functional Requirements

- **FR-01:** Holding the configured hotkey records speech; releasing it stops recording.
- **FR-02:** Speech-to-text is local by default.
- **FR-03:** The transcript is editable before submission.
- **FR-04:** The final prompt is passed to OpenCode through a configurable adapter.
- **FR-05:** Recurring corrections can be learned and persisted.
- **FR-06:** A project/user glossary can protect technical terms and names.
- **FR-07:** Learned rules are inspectable, editable, disableable, and deletable.
- **FR-08:** Microphone selection is configurable and persisted.

## Whisper Model Strategy

Model selection must be configurable. Start with a balanced English model, benchmark 20-30 real prompts, and choose the smallest model that meets the required accuracy. Candidate profiles:

- **Fast:** `small.en` / `small`
- **Balanced:** `medium.en` or a suitable distilled large model
- **Accuracy:** `large-v3`

## Correction-Based Speaker Adaptation

Whisper itself is not retrained in v0.1. Adaptation happens around it:

- **Static glossary:** canonical technical terms and project names.
- **Learned alias map:** e.g. a recurring misrecognition can map to the intended term after confirmation.
- **Context rules:** replacements can depend on nearby words/category rather than applying globally.

### Safety rules

- Do not learn an ambiguous replacement from a single accidental edit without confirmation.
- Raw audio is not persisted by default.
- Full prompt text need not be stored in correction history.
- Use word/phrase-boundary matching, never uncontrolled substring replacement.
- Provide a one-shot bypass of learned substitutions.

## OpenCode Integration

Current OpenCode documentation supports scriptable prompt submission with `opencode run [message..]`, including attachment to a running server. The adapter should support at least:

- `opencode run <prompt>`
- `opencode run --attach <server> <prompt>`

Do not make terminal keystroke injection the primary integration mechanism. It is more fragile and can be added later only if direct insertion into an already-open interactive TUI is specifically required.

## Proposed Project Structure

```text
opencode-voice/
  src/
    app.py
    audio.py
    transcriber.py
    adaptation.py
    hotkeys.py
    ui_review.py
    storage.py
    adapters/
      opencode.py
  tests/
  scripts/
  data/
    adaptation.db
  config.example.toml
  requirements.txt
  PROJECT.md
```

## Development Roadmap

### Phase 0 - Spike

Mic capture, hotkey state machine, faster-whisper setup, CUDA/CPU check, and transcription benchmark.

### Phase 1 - MVP

Push-to-talk -> transcription -> editable review -> OpenCode send/cancel.

### Phase 2 - Adaptation

SQLite glossary, learned corrections, context-aware substitutions, and a small vocabulary manager.

### Phase 3 - Desktop Polish

Tray application, settings window, diagnostics, microphone/model selection, and Windows autostart.

### Phase 4 - Packaging

Pinned dependencies, clean-machine install test, PyInstaller build, regression tests.

### Phase 5 - Extensions

Additional adapters for other CLI/editor/agent tools while retaining the same voice layer.

## v0.1 Acceptance Gate

The draft becomes a working v0.1 when:

- push-to-talk works reliably;
- transcripts can always be edited before submission;
- prompts can be sent to OpenCode through the adapter;
- raw audio is not retained by default;
- a recurring misrecognition can be learned, inspected, and corrected automatically later;
- 100 consecutive dictate/cancel/send cycles complete without a crash.

## References

- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- OpenCode CLI: https://dev.opencode.ai/docs/cli
- CTranslate2 installation: https://github.com/OpenNMT/CTranslate2/blob/master/docs/installation.md
