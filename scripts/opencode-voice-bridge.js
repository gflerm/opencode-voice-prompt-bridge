// OpenCode Voice Prompt Bridge - companion plugin.
// Auto-loaded by OpenCode at startup from ~/.config/opencode/plugins/.
// Polls the local voice bridge (Python app) and inserts dictated text
// into this prompt via the TUI API - no synthetic keystrokes.
// Port can be overridden with the VOICE_BRIDGE_PORT environment variable.

const PORT = process.env.VOICE_BRIDGE_PORT || "8765"
const BASE = `http://127.0.0.1:${PORT}`

export const VoiceBridgePlugin = async ({ client }) => {
  let lastId = 0
  let lastStatus = ""

  const toast = async (message, variant) => {
    try {
      await client.tui.showToast({ body: { message, variant } })
    } catch {}
  }

  const poll = async () => {
    let state
    try {
      const res = await fetch(`${BASE}/state?since=${lastId}`)
      if (!res.ok) return
      state = await res.json()
    } catch {
      return // bridge not running - stay silent
    }

    if (state.status !== lastStatus) {
      const previous = lastStatus
      lastStatus = state.status
      if (state.status === "recording" && previous !== "recording") {
        await toast("voice: recording...", "info")
      }
    }

    if (state.event === "transcript" && state.id > lastId && state.text) {
      try {
        await client.tui.appendPrompt({ body: { text: state.text } })
        await toast("voice: text inserted - review and press Enter", "success")
      } catch {}
      lastId = state.id
    }
  }

  const timer = setInterval(() => {
    poll()
  }, 400)
  if (typeof timer.unref === "function") timer.unref()

  return {}
}
