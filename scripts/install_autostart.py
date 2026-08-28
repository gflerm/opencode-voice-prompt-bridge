"""Register (or remove) the voice bridge in the Windows per-user Run key.

Usage:
  .venv\\Scripts\\python.exe scripts\\install_autostart.py            # install
  .venv\\Scripts\\python.exe scripts\\install_autostart.py --remove   # remove
  .venv\\Scripts\\python.exe scripts\\install_autostart.py --status   # show entry

The entry launches .venv\\Scripts\\pythonw.exe src\\app.py at login
(windowless: tray icon only; prints go to data/app.log). Remove with
--remove or via the tray icon's Quit plus --remove.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OpenCodeVoiceBridge"


def build_command() -> str:
    """The quoted pythonw + app.py command line stored in the Run key."""
    pythonw = REPO_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    app_py = REPO_ROOT / "src" / "app.py"
    if not pythonw.exists():
        raise SystemExit(f"pythonw.exe not found at {pythonw} - create the venv first")
    if not app_py.exists():
        raise SystemExit(f"app.py not found at {app_py}")
    return f'"{pythonw}" "{app_py}"'


def install() -> None:
    import winreg

    command = build_command()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    print(f"installed: {VALUE_NAME} = {command}")
    print("windowless mode - logs: data/app.log; exit via the tray icon")


def remove() -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            print("not installed - nothing to remove")
            return
    print(f"removed: {VALUE_NAME}")


def status() -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _type = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        print("not installed")
        return
    print(f"{VALUE_NAME} = {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/remove the login autostart entry.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--remove", action="store_true", help="delete the Run entry")
    group.add_argument("--status", action="store_true", help="show the Run entry")
    args = parser.parse_args()
    if args.remove:
        remove()
    elif args.status:
        status()
    else:
        install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
