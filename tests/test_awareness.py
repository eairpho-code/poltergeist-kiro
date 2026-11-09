"""How a human's actions reach the agent: GET /human-actions, the watcher and the Claude Code hook."""

import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from poltergeist import server
from poltergeist.action_log import ActionLog
from poltergeist.activity import describe_action, describe_activity, describe_mismatch
from poltergeist.claude_hook import (
    CursorStore,
    Server,
    agent_gesture,
    handle_event,
    is_simulator_tool,
    main as hook_main,
)
from poltergeist.watch import Watcher

SIM_TOOL = "mcp__Claude_Code_iOS_Simulator__control"


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.delenv("POLTERGEIST_REDACT_UI_LABELS", raising=False)
    fake = FakeClock()
    monkeypatch.setattr(server, "action_log", ActionLog(clock=fake))
    return fake


@pytest.fixture
def http():
    with TestClient(server.mcp.streamable_http_app()) as client:
        yield client


class HttpServer(Server):
    """The hook's Server, talking to the in-process app instead of a socket."""

    def __init__(self, http):
        super().__init__("http://testserver")
        self._http = http

    def record_agent(self, body):
        self._http.post("/agent-click", json=body).raise_for_status()

    def human_actions(self, since):
        params = {"since": since} if since else {}
        response = self._http.get("/human-actions", params=params)
        response.raise_for_status()
        return response.json()


def human_click(http, x, y):
    return http.post("/human-click", json={
        "x": x, "y": y, "coordinate_space": "device_points", "scale_factor": 1,
    }).json()


def human_drag(http, x, y, end_x, end_y):
    return http.post("/human-click", json={
        "x": x, "y": y, "end_x": end_x, "end_y": end_y,
        "coordinate_space": "device_points", "scale_factor": 1,
    }).json()


# --- GET /human-actions ------------------------------------------------------

def test_the_read_route_returns_what_the_tool_returns(clock, http):
    human_click(http, 10, 20)

    body = http.get("/human-actions").json()

    assert body["human_actions"] == server.get_human_actions()["human_actions"]
    assert set(body) == {"human_actions", "mismatches", "coordinate_scale_problem", "server_time"}


def test_server_time_comes_from_the_servers_clock(clock, http):
    assert http.get("/human-actions").json()["server_time"] == "2026-05-15T14:30:00.000Z"


def test_since_returns_only_later_actions(clock, http):
    first = human_click(http, 1, 1)
    clock.advance(2)
    second = human_click(http, 2, 2)

    body = http.get("/human-actions", params={"since": first["timestamp"]}).json()

    assert [a["timestamp"] for a in body["human_actions"]] == [second["timestamp"]]


def test_a_bad_since_is_a_400_with_the_reason(clock, http):
    response = http.get("/human-actions", params={"since": "yesterday"})
    assert response.status_code == 400
    assert "timestamp must be UTC ISO 8601" in response.json()["error"]


def test_the_read_route_never_changes_the_log(clock, http):
    human_click(http, 1, 1)
    http.get("/human-actions")
    http.get("/human-actions")
    assert len(server.action_log._actions) == 1


# --- Descriptions ------------------------------------------------------------

def _action(**overrides):
    action = {
        "timestamp": "2026-05-15T14:30:41.000Z", "actor": "human", "kind": "click",
        "normalized_x": 110.0, "normalized_y": 105.0, "end_x": None, "end_y": None,
        "ui_element": None,
    }
    action.update(overrides)
    return action


def test_a_click_is_described_with_its_position_and_time():
    assert describe_action(_action()) == "the human clicked (110.0, 105.0) at 14:30:41 UTC"


def test_a_click_names_the_element_role_when_known():
    text = describe_action(_action(ui_element={"role": "button", "label": None}))
    assert "on a button" in text


def test_a_drag_is_described_from_start_to_end():
    text = describe_action(_action(kind="drag", end_x=232.67, end_y=529.45))
    assert text == "the human dragged from (110.0, 105.0) to (232.7, 529.5) at 14:30:41 UTC"


def test_a_mismatch_says_how_long_after_and_how_far_off():
    agent = _action(actor="agent", timestamp="2026-05-15T14:30:43.200Z", normalized_x=181.6, normalized_y=52.8)
    human = _action(timestamp="2026-05-15T14:30:47.700Z", normalized_x=361.5, normalized_y=432.6)
    text = describe_mismatch({
        "agent_click": agent, "human_click": human, "offset_x": 179.9, "offset_y": 379.8,
    })
    assert "came 4.5s after the agent's click at (181.6, 52.8)" in text
    assert "offset (+179.9, +379.8)" in text


def test_a_scale_problem_is_reported_in_words():
    lines = describe_activity({
        "human_actions": [], "mismatches": [],
        "coordinate_scale_problem": {"scale_x": 2.0, "scale_y": 2.01, "sample_size": 5},
    })
    assert len(lines) == 1
    assert "x2.00 horizontally" in lines[0] and "5 samples" in lines[0]


def test_nothing_to_report_is_no_lines():
    assert describe_activity({"human_actions": [], "mismatches": [], "coordinate_scale_problem": None}) == []


# --- The watcher -------------------------------------------------------------

def _watcher(http):
    def fetch(since):
        params = {"since": since} if since else {}
        return http.get("/human-actions", params=params).json()

    return Watcher(fetch)


def test_the_watcher_starts_from_now_and_ignores_history(clock, http):
    human_click(http, 1, 1)
    clock.advance(5)
    watcher = _watcher(http)
    watcher.start()

    assert watcher.poll() == []


def test_the_watcher_reports_each_new_action_once(clock, http):
    watcher = _watcher(http)
    watcher.start()
    clock.advance(1)
    human_click(http, 10, 20)

    first = watcher.poll()
    again = watcher.poll()

    assert len(first) == 1 and "clicked (10.0, 20.0)" in first[0]
    assert again == []


def test_the_watcher_reports_drags_and_the_mismatch_they_follow(clock, http):
    watcher = _watcher(http)
    watcher.start()
    clock.advance(1)
    http.post("/agent-click", json={"x": 100, "y": 100, "coordinate_space": "device_points", "scale_factor": 1})
    clock.advance(2)
    human_click(http, 110, 105)
    clock.advance(10)
    human_drag(http, 200, 800, 200, 300)

    lines = watcher.poll()

    assert any("clicked (110.0, 105.0)" in line for line in lines)
    assert any("came 2.0s after the agent's click" in line for line in lines)
    assert any("dragged from (200.0, 800.0) to (200.0, 300.0)" in line for line in lines)


# --- The Claude Code hook ----------------------------------------------------

def test_only_the_simulator_tool_is_recognised():
    assert is_simulator_tool(SIM_TOOL)
    assert is_simulator_tool("mcp__ios_simulator__tap")
    assert not is_simulator_tool("Bash")
    assert not is_simulator_tool("mcp__ccd_session__start_session")


@pytest.mark.parametrize("tool_input, expected", [
    ({"action": "tap", "x": 215, "y": 40},
     {"x": 215.0, "y": 40.0}),
    ({"action": "swipe", "x": 215, "y": 800, "x2": 215, "y2": 300},
     {"x": 215.0, "y": 800.0, "end_x": 215.0, "end_y": 300.0}),
    ({"action": "touch_path", "points": [{"x": 10, "y": 20}, {"x": 11, "y": 90}, {"x": 12, "y": 400}]},
     {"x": 10.0, "y": 20.0, "end_x": 12.0, "end_y": 400.0}),
    ({"action": "touch_path", "points": [{"x": 10, "y": 20}]},
     {"x": 10.0, "y": 20.0}),
])
def test_taps_and_swipes_become_agent_gestures(tool_input, expected):
    gesture = agent_gesture(tool_input)
    assert gesture["coordinate_space"] == "device_points"
    assert gesture["scale_factor"] == 1.0
    for key, value in expected.items():
        assert gesture[key] == value


@pytest.mark.parametrize("tool_input", [
    {"action": "screenshot"},
    {"action": "launch", "app_path": "/x.app"},
    {"action": "tap"},
    {"action": "tap", "x": "left", "y": 1},
    {"action": "touch_path", "points": []},
])
def test_other_actions_and_bad_input_are_not_recorded(tool_input):
    assert agent_gesture(tool_input) is None


def event(action_input, session="s1"):
    return {"session_id": session, "tool_name": SIM_TOOL, "tool_input": action_input}


def test_the_hook_records_the_agents_tap_on_the_server(clock, http, tmp_path):
    handle_event(event({"action": "tap", "x": 110, "y": 190}), HttpServer(http), CursorStore("s1", str(tmp_path)))

    [recorded] = server.action_log._actions
    assert recorded.actor == "agent"
    assert (recorded.normalized_x, recorded.normalized_y) == (110, 190)


def test_the_hook_says_nothing_on_its_first_call_even_if_there_is_history(clock, http, tmp_path):
    human_click(http, 5, 5)
    clock.advance(1)

    context = handle_event(event({"action": "screenshot"}), HttpServer(http), CursorStore("s1", str(tmp_path)))

    assert context is None


def test_the_hook_tells_the_agent_what_the_human_did_since_its_last_call(clock, http, tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = HttpServer(http)
    handle_event(event({"action": "tap", "x": 110, "y": 190}), hook, cursor)  # first call: just starts the clock
    clock.advance(1)
    human_click(http, 115, 180)
    clock.advance(1)

    context = handle_event(event({"action": "screenshot"}), hook, cursor)

    assert context.startswith("Poltergeist: since your last simulator action")
    assert "the human clicked (115.0, 180.0)" in context
    assert "after the agent's click at (110.0, 190.0)" in context
    assert "offset (+5.0, -10.0)" in context


def test_the_hook_reports_a_human_drag(clock, http, tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = HttpServer(http)
    handle_event(event({"action": "screenshot"}), hook, cursor)
    clock.advance(1)
    human_drag(http, 215, 800, 215, 300)

    context = handle_event(event({"action": "screenshot"}), hook, cursor)

    assert "the human dragged from (215.0, 800.0) to (215.0, 300.0)" in context


def test_the_hook_reports_each_human_action_only_once(clock, http, tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = HttpServer(http)
    handle_event(event({"action": "screenshot"}), hook, cursor)
    clock.advance(1)
    human_click(http, 1, 1)

    assert handle_event(event({"action": "screenshot"}), hook, cursor) is not None
    assert handle_event(event({"action": "screenshot"}), hook, cursor) is None


def test_the_agents_own_taps_are_never_reported_back_to_it(clock, http, tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = HttpServer(http)
    handle_event(event({"action": "screenshot"}), hook, cursor)
    clock.advance(1)

    assert handle_event(event({"action": "tap", "x": 1, "y": 1}), hook, cursor) is None


def test_sessions_keep_separate_cursors(clock, http, tmp_path):
    hook = HttpServer(http)
    a, b = CursorStore("a", str(tmp_path)), CursorStore("b", str(tmp_path))
    handle_event(event({"action": "screenshot"}, "a"), hook, a)
    clock.advance(1)
    human_click(http, 1, 1)
    handle_event(event({"action": "screenshot"}, "b"), hook, b)  # b starts after the click

    assert handle_event(event({"action": "screenshot"}, "a"), hook, a) is not None
    assert handle_event(event({"action": "screenshot"}, "b"), hook, b) is None


def test_other_tools_are_ignored_without_touching_the_server(tmp_path):
    class Exploding(Server):
        def record_agent(self, body):
            raise AssertionError("must not be called")

        def human_actions(self, since):
            raise AssertionError("must not be called")

    context = handle_event({"tool_name": "Bash", "tool_input": {"command": "ls"}},
                           Exploding("http://x"), CursorStore("s", str(tmp_path)))
    assert context is None


def test_an_unreachable_server_never_breaks_the_hook(tmp_path):
    stdin = io.StringIO(json.dumps(event({"action": "tap", "x": 1, "y": 1})))
    stdout = io.StringIO()

    code = hook_main(stdin, stdout, {"POLTERGEIST_URL": "http://127.0.0.1:1", "POLTERGEIST_HOOK_STATE_DIR": str(tmp_path)})

    assert code == 0
    assert stdout.getvalue() == ""


def test_garbage_on_stdin_never_breaks_the_hook():
    assert hook_main(io.StringIO("not json"), io.StringIO(), {}) == 0


def test_the_hook_prints_context_in_the_shape_claude_code_expects(clock, http, tmp_path, monkeypatch):
    cursor_dir = str(tmp_path)
    hook = HttpServer(http)
    handle_event(event({"action": "screenshot"}), hook, CursorStore("s1", cursor_dir))
    clock.advance(1)
    human_click(http, 7, 8)

    monkeypatch.setattr("poltergeist.claude_hook.Server", lambda url: hook)
    stdout = io.StringIO()
    code = hook_main(io.StringIO(json.dumps(event({"action": "screenshot"}))), stdout,
                     {"POLTERGEIST_HOOK_STATE_DIR": cursor_dir})

    assert code == 0
    output = json.loads(stdout.getvalue())
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "the human clicked (7.0, 8.0)" in output["hookSpecificOutput"]["additionalContext"]
