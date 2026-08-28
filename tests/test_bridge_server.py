"""Voice bridge state server tests."""

from pathlib import Path
import json
import sys
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from bridge_server import VoiceBridgeServer, VoiceBridgeState


def test_state_starts_idle():
    state = VoiceBridgeState()
    snap = state.snapshot(since=0)
    assert snap["status"] == "idle"
    assert snap["event"] is None


def test_publish_increments_ids_and_since_semantics():
    state = VoiceBridgeState()
    first = state.publish_transcript("one")
    second = state.publish_transcript("two")

    assert (first, second) == (1, 2)
    stale = state.snapshot(since=second)
    assert stale["event"] is None

    fresh = state.snapshot(since=0)
    assert fresh["event"] == "transcript"
    assert fresh["text"] == "two"
    assert fresh["fetches"] == 1


def test_fetches_counter_tracks_deliveries():
    state = VoiceBridgeState()
    event_id = state.publish_transcript("hello")
    state.snapshot(since=0)
    state.snapshot(since=0)
    assert state.fetches_for(event_id) == 2
    assert state.fetches_for(999) == -1


def test_status_transitions():
    state = VoiceBridgeState()
    state.set_status("recording")
    assert state.snapshot(since=0)["status"] == "recording"
    state.set_status("transcribing")
    assert state.snapshot(since=0)["status"] == "transcribing"


def test_http_roundtrip():
    server = VoiceBridgeServer(port=0)
    server.start()
    try:
        assert server.port > 0
        server.state.set_status("recording")
        server.state.publish_transcript("round trip text")
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.port}/state?since=0", timeout=5
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "recording"
        assert data["event"] == "transcript"
        assert data["text"] == "round trip text"
        assert data["fetches"] == 1
    finally:
        server.stop()
