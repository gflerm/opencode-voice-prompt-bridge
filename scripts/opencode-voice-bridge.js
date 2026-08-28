// OpenCode Voice Prompt Bridge - companion plugin.
// Auto-loaded by OpenCode at startup from ~/.config/opencode/plugins/.
// Polls the local voice bridge (Python app) and inserts dictated text
// into this prompt via the TUI API - no synthetic keystrokes.
// Port can be overridden with the VOICE_BRIDGE_PORT environment variable.
//
// Polling uses node:http with keepAlive: false. The Python app is
// restarted routinely (tray Quit, autostart); a pooled keep-alive
// socket to the dead instance would otherwise fail silently forever.

import http from "node:http"

const PORT = process.env.VOICE_BRIDGE_PORT || "8765"
const POLL_MS = 400

export const VoiceBridgePlugin = async ({ client }) => {
  let lastId = 0
  let lastStatus = ""
  let failures = 0

  const agent = new http.Agent({ keepAlive: false })

  const log = async (level, message) => {
    try {
      await client.app.log({ body: { service: "voice-bridge", level, message } })
    } catch {}
  }

  const toast = async (message, variant) => {
    try {
      await client.tui.showToast({ body: { message, variant } })
    } catch {}
  }

  const fetchState = () =>
    new Promise((resolve) => {
      const req = http.get(
        { host: "127.0.0.1", port: PORT, path: `/state?since=${lastId}`, agent },
        (res) => {
          let data = ""
          res.on("data", (chunk) => (data += chunk))
          res.on("end", () => {
            try {
              resolve(JSON.parse(data))
            } catch {
              resolve(null)
            }
          })
        }
      )
      req.on("error", () => resolve(null))
      req.setTimeout(1000, () => {
        req.destroy()
        resolve(null)
      })
    })

  const poll = async () => {
    const state = await fetchState()
    if (!state) {
      failures += 1
      if (failures === 1 || failures % 50 === 0) {
        await log("warn", `bridge unreachable (x${failures}) - is the voice app running?`)
      }
      return
    }
    if (failures) {
      await log("info", `bridge reachable again after ${failures} failed poll(s)`)
      failures = 0
    }

    if (state.status !== lastStatus) {
      const previous = lastStatus
      lastStatus = state.status
      if (state.status === "recording" && previous !== "recording") {
        await toast("voice: recording...", "info")
      }
    }

    if (state.id < lastId) {
      // Bridge restarted with fresh ids - resync instead of ignoring
      // everything below our stale marker.
      lastId = 0
    }

    if (state.event === "transcript" && state.id > lastId && state.text) {
      try {
        await client.tui.appendPrompt({ body: { text: state.text } })
        await toast("voice: text inserted - review and press Enter", "success")
      } catch {}
      lastId = state.id
    }
  }

  const timer = setInterval(poll, POLL_MS)
  if (typeof timer.unref === "function") timer.unref()
  await log("info", `polling 127.0.0.1:${PORT} every ${POLL_MS}ms`)
  return {}
}
