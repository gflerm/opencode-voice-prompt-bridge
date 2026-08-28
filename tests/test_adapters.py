"""OpenCode adapter tests (subprocess is faked)."""

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters import opencode as adapter
from config import OpencodeConfig


def make_config(**overrides) -> OpencodeConfig:
    values = dict(command="opencode", mode="run", attach_server="", show_console=False, working_dir="")
    values.update(overrides)
    return OpencodeConfig(**values)


def test_build_args_run_mode():
    args = adapter.build_args(make_config(), "hello world")
    assert args == ["opencode", "run", "hello world"]


def test_build_args_attach_mode():
    args = adapter.build_args(make_config(mode="attach", attach_server="127.0.0.1:4096"), "hi")
    assert args == ["opencode", "run", "--attach", "127.0.0.1:4096", "hi"]


def test_build_args_rejects_empty_prompt():
    with pytest.raises(adapter.AdapterError):
        adapter.build_args(make_config(), "   ")


def test_build_args_rejects_unknown_mode():
    with pytest.raises(adapter.AdapterError):
        adapter.build_args(make_config(mode=" Carrier pigeon "), "hi")


def test_build_args_attach_requires_server():
    with pytest.raises(adapter.AdapterError):
        adapter.build_args(make_config(mode="attach"), "hi")


def test_send_wait_success(monkeypatch):
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return type("R", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    code = adapter.send(make_config(), "hello", wait=True)
    assert code == 0
    assert calls["args"] == ["opencode", "run", "hello"]


def test_send_wait_nonzero_raises(monkeypatch):
    def fake_run(args, **kwargs):
        return type("R", (), {"returncode": 3, "stderr": "boom"})()

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    with pytest.raises(adapter.AdapterError, match="exited 3"):
        adapter.send(make_config(), "hello", wait=True)


def test_send_missing_executable(monkeypatch):
    def fake_run(args, **kwargs):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    with pytest.raises(adapter.AdapterError, match="executable not found"):
        adapter.send(make_config(), "hello", wait=True)


def test_send_fire_and_forget(monkeypatch):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        return "fake-process"

    monkeypatch.setattr(adapter.subprocess, "Popen", fake_popen)
    result = adapter.send(make_config(), "dictated prompt")
    assert result == "fake-process"
    assert captured["args"] == ["opencode", "run", "dictated prompt"]
