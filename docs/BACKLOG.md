# Backlog - OpenCode Voice Prompt Bridge

Ideas and requests beyond the current spec phases. Newest first.

## Native-mode learning box (requested 2026-08-28, shelved)

In native + direct-send mode dictations bypass the review window, so
edits made in the OpenCode prompt are never learned as correction
pairs (FR-05 only fires from the review window).

Sketch (build only if inline fixes start feeling tedious):
- Small always-on-top side box shown after each dictation, prefilled
  with the adapted transcript; Enter learns diff_pairs(original, edited)
  via AdaptationEngine, Esc closes; nothing is ever sent from it.
- Must not steal focus from the TUI (reactivate the captured target
  window after showing; widget-local key bindings only).
- Queue like ReviewManager when a new dictation arrives while open.
- Skip when the fallback review window already covers the utterance.

Decision 2026-08-28: shelved - glossary terms (vocab_manager.py) cover
recurring jargon without seeing edits; inline fixing is fine for now.

## Assistant-response filtering (requested 2026-08-28)

When OpenCode replies, the TUI shows everything: tool calls, thinking,
code edits, diffs. The user wants an option to receive only the final
prose answer - no tool noise - for voice-style interaction.

Sketch (build later, do not implement now):
- The companion plugin already runs inside OpenCode; it can subscribe to
  `session.idle` / `message.part.updated` events and fetch the finished
  assistant message via `client.session.messages`.
- Filter to the last assistant text part (skip tool-call parts, thinking
  blocks, diffs).
- Surface options: toast summary in the TUI, or optional TTS readback
  (would add a voice-output layer - currently a non-goal for v0.1).
- Config idea: `[output] response_mode = "off" | "toast" | "tts"`.

Related: auto-listen after `session.idle` (agent finishes -> bridge
arms recording) would make the loop conversational.

## Other open items

- Spec section 14 reliability soak: 100 consecutive dictate/cancel/send
  cycles without crash (Phase 1 gate, still pending).
- Phase 3 remainder: settings GUI (tray icon and Windows autostart are
  done: tray toggles for hotkey + OpenCode binding, HKCU Run installer).
