"""OpenCode CLI adapter: hands off a final prompt via subprocess."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from config import OpencodeConfig


class AdapterError(RuntimeError):
    """Raised when the OpenCode handoff cannot be performed."""


def build_args(config: OpencodeConfig, prompt: str) -> list[str]:
    """Build the argument array for the OpenCode invocation."""
    if not prompt.strip():
        raise AdapterError("refusing to send an empty prompt")
    mode = config.mode.strip().lower()
    if mode not in ("run", "attach"):
        raise AdapterError(f"unknown opencode mode: {config.mode!r}")
    args = [config.command, "run"]
    if mode == "attach":
        if not config.attach_server.strip():
            raise AdapterError("attach mode requires opencode.attach_server in config")
        args += ["--attach", config.attach_server]
    args.append(prompt)
    return args


def _console_flags(config: OpencodeConfig) -> int:
    if sys.platform == "win32" and config.show_console:
        return subprocess.CREATE_NEW_CONSOLE
    return 0


def send(config: OpencodeConfig, prompt: str, wait: bool = False) -> subprocess.Popen | int:
    """Launch the OpenCode handoff.

    Default is fire-and-forget (Popen) so the voice loop stays responsive;
    opencode may stream a long agent reply in its own console. With
    wait=True the process is awaited and non-zero exits raise.
    """
    args = build_args(config, prompt)
    flags = _console_flags(config)
    try:
        if wait:
            completed = subprocess.run(
                args,
                creationflags=flags,
                cwd=config.working_dir or None,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                stderr = (completed.stderr or "").strip()
                raise AdapterError(
                    f"{config.command} exited {completed.returncode}"
                    + (f": {stderr[:200]}" if stderr else "")
                )
            return completed.returncode
        return subprocess.Popen(
            args,
            creationflags=flags,
            cwd=config.working_dir or None,
        )
    except FileNotFoundError as exc:
        raise AdapterError(f"executable not found: {config.command!r}") from exc
    except OSError as exc:
        raise AdapterError(f"failed to launch {config.command!r}: {exc}") from exc
