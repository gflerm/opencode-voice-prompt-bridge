# Backlog - OpenCode Voice Prompt Bridge

Ideas and requests beyond the current spec phases. Newest first.

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
- Phase 3: tray icon with state, settings GUI, Windows autostart.
