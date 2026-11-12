"""Tests for the Kiro recorder hook (poltergeist/kiro_hook.py)."""

import io
import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from poltergeist import kiro_hook


class _Stub:
    """A tiny HTTP server that records the requests it gets."""

    def __init__(self, delay: float = 0.0) -> None:
        stub = self
        self.requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                stub.requests.append((self.path, body))
                if delay:
                    time.sleep(delay)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    s = _Stub()
    yield s
    s.close()


def _event(name, tool_input=None, **extra):
    event = {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "cwd": "/tmp",
        "tool_name": name,
    }
    if tool_input is not None:
        event["tool_input"] = tool_input
    event.update(extra)
    return event


def _run(event, url):
    """Run main() in-process; return (exit code, requests are on the stub)."""
    text = event if isinstance(event, str) else json.dumps(event)
    return kiro_hook.main(io.StringIO(text), {kiro_hook.URL_ENV_VAR: url}, [])


def _tap(x, y):
    return {"x": x, "y": y, "coordinate_space": "device_points", "scale_factor": 1}


def test_tap_is_recorded(stub):
    assert _run(_event("mcp_ios_simulator_ui_tap", {"x": 150, "y": 300}), stub.url) == 0
    assert stub.requests == [("/agent-click", _tap(150, 300))]


def test_tap_floats_are_sent_as_they_are(stub):
    _run(_event("mcp_ios_simulator_ui_tap", {"x": 150.5, "y": 300.25}), stub.url)
    assert stub.requests == [("/agent-click", _tap(150.5, 300.25))]


def test_tap_ignores_other_fields(stub):
    _run(
        _event("mcp_ios_simulator_ui_tap", {"x": 1, "y": 2, "duration": "0.5", "udid": "u"}),
        stub.url,
    )
    assert stub.requests == [("/agent-click", _tap(1, 2))]


@pytest.mark.parametrize(
    "name",
    [
        "mcp_ios_simulator_ui_tap",
        "@ios-simulator/ui_tap",
        "mcp__ios-simulator__ui_tap",
        "MCP_iOS_Simulator_UI_Tap",
        "ui_tap",
    ],
)
def test_tap_name_forms(stub, name):
    _run(_event(name, {"x": 5, "y": 6}), stub.url)
    assert stub.requests == [("/agent-click", _tap(5, 6))]


def test_post_tool_use_event_is_recorded_too(stub):
    event = _event(
        "mcp_ios_simulator_ui_tap",
        {"x": 7, "y": 8},
        hook_event_name="PostToolUse",
        tool_response="Tapped",
    )
    _run(event, stub.url)
    assert stub.requests == [("/agent-click", _tap(7, 8))]


def test_swipe_is_recorded_as_a_drag(stub):
    event = _event(
        "mcp_ios_simulator_ui_swipe",
        {"x_start": 10, "y_start": 20, "x_end": 200, "y_end": 400,
         "duration": "0.3", "delta": 1, "udid": "u"},
    )
    assert _run(event, stub.url) == 0
    assert stub.requests == [
        (
            "/agent-click",
            {"x": 10, "y": 20, "end_x": 200, "end_y": 400,
             "coordinate_space": "device_points", "scale_factor": 1},
        )
    ]


IGNORED = {
    "screenshot": _event("mcp_ios_simulator_screenshot", {"output_path": "a.png"}),
    "describe": _event("mcp_ios_simulator_ui_describe_all", {}),
    "other tool": _event("read_file", {"path": "a"}),
    "tap without x": _event("mcp_ios_simulator_ui_tap", {"y": 3}),
    "tap with string": _event("mcp_ios_simulator_ui_tap", {"x": "150", "y": 300}),
    "tap with boolean": _event("mcp_ios_simulator_ui_tap", {"x": True, "y": 300}),
    "tap with null": _event("mcp_ios_simulator_ui_tap", {"x": None, "y": 300}),
    "swipe missing an end": _event(
        "mcp_ios_simulator_ui_swipe", {"x_start": 1, "y_start": 2, "x_end": 3}
    ),
    "swipe with boolean": _event(
        "mcp_ios_simulator_ui_swipe",
        {"x_start": 1, "y_start": 2, "x_end": 3, "y_end": False},
    ),
    "input is a list": _event("mcp_ios_simulator_ui_tap", [1, 2]),
    "no input": _event("mcp_ios_simulator_ui_tap"),
    "no name": _event(None, {"x": 1, "y": 2}),
    "name not a string": {"tool_name": 7, "tool_input": {"x": 1, "y": 2}},
    "tap-like suffix only": _event("mcp_ios_simulator_ui_tap_all", {"x": 1, "y": 2}),
    "not json": "this is not json",
    "empty": "",
    "json list": "[]",
    "json null": "null",
    "json number": "5",
}


@pytest.mark.parametrize("label", sorted(IGNORED))
def test_ignored_events_send_nothing(stub, label):
    assert _run(IGNORED[label], stub.url) == 0
    assert stub.requests == []


def test_non_finite_numbers_are_ignored(stub):
    text = '{"tool_name": "ui_tap", "tool_input": {"x": NaN, "y": Infinity}}'
    assert _run(text, stub.url) == 0
    assert stub.requests == []


def test_gesture_from_event_returns_none_for_non_dict():
    assert kiro_hook.gesture_from_event(None) is None
    assert kiro_hook.gesture_from_event([]) is None


def test_address_comes_from_environment_and_trailing_slash_is_fine(stub):
    _run(_event("ui_tap", {"x": 1, "y": 2}), stub.url + "/")
    assert stub.requests == [("/agent-click", _tap(1, 2))]


def test_default_address():
    assert kiro_hook.DEFAULT_URL == "http://127.0.0.1:8000"
    assert kiro_hook.URL_ENV_VAR == "POLTERGEIST_URL"


def test_timeout_is_at_most_two_seconds():
    assert kiro_hook.TIMEOUT_SECONDS <= 2.0


def test_unreachable_server_exits_zero():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    event = _event("mcp_ios_simulator_ui_tap", {"x": 1, "y": 2})
    assert _run(event, f"http://127.0.0.1:{port}") == 0


def test_bad_address_exits_zero():
    event = _event("mcp_ios_simulator_ui_tap", {"x": 1, "y": 2})
    assert _run(event, "not a url") == 0


def _subprocess(text, url):
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "poltergeist.kiro_hook"],
        input=text,
        capture_output=True,
        text=True,
        env={"POLTERGEIST_URL": url, "PATH": ""},
        timeout=30,
    )
    return result, time.monotonic() - started


def test_module_runs_quietly_and_records(stub):
    event = json.dumps(_event("mcp_ios_simulator_ui_tap", {"x": 9, "y": 10}))
    result, _ = _subprocess(event, stub.url)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert stub.requests == [("/agent-click", _tap(9, 10))]


def test_module_is_quiet_on_garbage(stub):
    result, _ = _subprocess("garbage", stub.url)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert stub.requests == []


def test_module_is_quiet_when_server_is_down():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    event = json.dumps(_event("mcp_ios_simulator_ui_tap", {"x": 1, "y": 2}))
    result, _ = _subprocess(event, f"http://127.0.0.1:{port}")
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


def test_slow_server_does_not_hang_the_agent():
    slow = _Stub(delay=10)
    try:
        event = json.dumps(_event("mcp_ios_simulator_ui_tap", {"x": 1, "y": 2}))
        result, took = _subprocess(event, slow.url)
    finally:
        slow.server.shutdown()
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert took < 6


# --- shape of the example files in integrations/kiro ---

import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_KIRO = _ROOT / "integrations" / "kiro"


def test_hooks_file_shape():
    data = json.loads((_KIRO / "hooks" / "poltergeist.json").read_text())
    assert data["version"] == "v1"
    by_trigger = {h["trigger"]: h for h in data["hooks"]}
    assert len(data["hooks"]) == 2 and set(by_trigger) == {"PreToolUse", "PostToolUse"}
    pre, post = by_trigger["PreToolUse"], by_trigger["PostToolUse"]
    assert pre["action"]["type"] == "command"
    assert pre["action"]["command"] == (
        "/ABSOLUTE/PATH/TO/poltergeist-kiro-hook --url http://127.0.0.1:8000"
    )
    assert post["action"]["type"] == "agent"
    assert "get_human_actions" in post["action"]["prompt"]
    assert pre["matcher"] == post["matcher"] == "@ios-simulator"
    assert pre["name"] and post["name"]


def test_mcp_file_shape():
    servers = json.loads((_KIRO / "mcp.json").read_text())["mcpServers"]
    assert servers["poltergeist"]["url"].endswith("/mcp")
    assert servers["ios-simulator"]["command"] == "npx"
    assert servers["ios-simulator"]["args"] == ["-y", "ios-simulator-mcp"]


def test_steering_file_text():
    text = (_KIRO / "steering" / "poltergeist.md").read_text()
    assert "get_human_actions" in text and "since_timestamp" in text
    assert "mismatch" in text and "scale" in text


def test_console_script_declared():
    assert 'poltergeist-kiro-hook = "poltergeist.kiro_hook:main"' in (_ROOT / "pyproject.toml").read_text()


# --- the --url argument ---


def _run_args(event, argv, environ):
    return kiro_hook.main(io.StringIO(json.dumps(event)), environ, argv)


_TAP_EVENT = _event("mcp_ios_simulator_ui_tap", {"x": 3, "y": 4})


def test_url_argument_wins_over_environment(stub):
    assert _run_args(_TAP_EVENT, ["--url", stub.url], {"POLTERGEIST_URL": "http://127.0.0.1:1"}) == 0
    assert stub.requests == [("/agent-click", _tap(3, 4))]


def test_url_equals_form(stub):
    _run_args(_TAP_EVENT, [f"--url={stub.url}"], {"POLTERGEIST_URL": "http://127.0.0.1:1"})
    assert stub.requests == [("/agent-click", _tap(3, 4))]


def test_environment_used_without_argument(stub):
    _run_args(_TAP_EVENT, [], {"POLTERGEIST_URL": stub.url})
    assert stub.requests == [("/agent-click", _tap(3, 4))]


@pytest.mark.parametrize("argv", [["--url"], ["--url", ""], ["--url="], ["--url", "--bogus"]])
def test_url_without_value_falls_back_to_environment(stub, argv):
    assert _run_args(_TAP_EVENT, argv, {"POLTERGEIST_URL": stub.url}) == 0
    assert stub.requests == [("/agent-click", _tap(3, 4))]


def test_unknown_arguments_are_ignored(stub):
    _run_args(_TAP_EVENT, ["--bogus", "--url", stub.url, "extra"], {})
    assert stub.requests == [("/agent-click", _tap(3, 4))]


def test_url_from_args_values():
    assert kiro_hook.url_from_args([]) is None
    assert kiro_hook.url_from_args(["x", "--url", "http://a"]) == "http://a"
    assert kiro_hook.url_from_args(["--url=http://b"]) == "http://b"


def test_module_takes_url_argument(stub):
    result = subprocess.run(
        [sys.executable, "-m", "poltergeist.kiro_hook", "--url", stub.url],
        input=json.dumps(_TAP_EVENT),
        capture_output=True,
        text=True,
        env={"PATH": ""},
        timeout=30,
    )
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
    assert stub.requests == [("/agent-click", _tap(3, 4))]


def test_agent_file_shape():
    data = json.loads((_KIRO / "agents" / "simdriver.json").read_text())
    assert data["name"] == "simdriver"
    assert data["tools"] == data["allowedTools"] == ["@ios-simulator", "@poltergeist"]
    assert data["includeMcpJson"] is True
    assert data["resources"] == ["file://.kiro/steering/**/*.md"]
