"""Install (or update) the companion plugin into OpenCode's global plugins dir.

Usage:
  .venv\\Scripts\\python.exe scripts\\install_plugin.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SOURCE = REPO_ROOT / "scripts" / "opencode-voice-bridge.js"
PLUGIN_NAME = "opencode-voice-bridge.js"


def plugin_target() -> Path:
    return Path.home() / ".config" / "opencode" / "plugins" / PLUGIN_NAME


def main() -> int:
    if not PLUGIN_SOURCE.exists():
        print(f"missing plugin source: {PLUGIN_SOURCE}")
        return 1
    target = plugin_target()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PLUGIN_SOURCE, target)
    print(f"installed: {target}")
    print("restart OpenCode so the plugin loads (plugins load at startup)")
    print("the voice app must be running (mode = \"native\") for the plugin to receive dictations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
