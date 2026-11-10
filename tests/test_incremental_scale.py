"""The scale problem belongs to the whole log, and the watcher and the hook say it once.

Specification: .kiro/specs/incremental-scale/
"""

import json
from datetime import timedelta

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from poltergeist import server
from poltergeist.action_log import ActionLog
from poltergeist.activity import describe_activity, scale_changed
from poltergeist.claude_hook import CursorStore, Server, handle_event
from poltergeist.watch import Watcher
from tests.helpers import BASE_TIME, make_click, timestamp_at
from tests.test_awareness import (  # noqa: F401  (the fixtures are used by name)
    HttpServer,
    _watcher,
    clock,
    event,
    http,
    human_click,
)


def fixed_clock(ms: int):
    return lambda: BASE_TIME + timedelta(milliseconds=ms)


def three_corrections():
    """Three agent clicks, each corrected by a human click 1 s later; the agent is 1.5 times too big.

    The pairs are 10 s apart, so a click never falls in the window of another pair.
    """
    return [
        make_click("agent", 1000, 150, 300), make_click("human", 2000, 100, 200),
        make_click("agent", 12000, 225, 450), make_click("human", 13000, 150, 300),
        make_click("agent", 22000, 300, 150), make_click("human", 23000, 200, 100),
    ]


def log_with(actions):
    log = ActionLog(clock=fixed_clock(30000))
    log._actions = list(actions)
    return log


# --- Requirement 1: the log ---------------------------------------------------

def test_without_a_cursor_the_result_is_unchanged():
    result = log_with(three_corrections()).get_human_actions()

    assert len(result.human_actions) == 3
    assert len(result.mismatches) == 3
    assert result.coordinate_scale_problem.sample_size == 3
    assert result.coordinate_scale_problem.scale_x == pytest.approx(1.5)


def test_a_cursor_after_the_second_correction_still_names_the_scale_problem():
    result = log_with(three_corrections()).get_human_actions(since_timestamp=timestamp_at(13000))

    assert [a.timestamp for a in result.human_actions] == [timestamp_at(23000)]
    assert len(result.mismatches) == 1
    assert result.coordinate_scale_problem is not None
    assert result.coordinate_scale_problem.sample_size == 3
    assert result.coordinate_scale_problem.scale_y == pytest.approx(1.5)


def test_a_cursor_later_than_everything_returns_nothing_but_the_scale_problem():
    result = log_with(three_corrections()).get_human_actions(since_timestamp=timestamp_at(60000))

    assert result.human_actions == []
    assert result.mismatches == []
    assert result.coordinate_scale_problem.sample_size == 3


def test_the_cursor_is_still_exclusive():
    result = log_with(three_corrections()).get_human_actions(since_timestamp=timestamp_at(23000))

    assert result.human_actions == []
    assert result.mismatches == []


def test_two_corrections_are_not_a_scale_problem_whatever_the_cursor():
    log = log_with(three_corrections()[:4])

    assert log.get_human_actions().coordinate_scale_problem is None
    assert log.get_human_actions(since_timestamp=timestamp_at(0)).coordinate_scale_problem is None


def test_the_read_route_gives_the_scale_problem_with_a_cursor(clock, http):
    server.action_log._actions = three_corrections()

    answer = http.get("/human-actions", params={"since": timestamp_at(13000)}).json()

    assert len(answer["human_actions"]) == 1
    assert answer["coordinate_scale_problem"]["sample_size"] == 3
    assert answer["coordinate_scale_problem"]["scale_x"] == pytest.approx(1.5)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    steps=st.lists(
        st.tuples(
            st.sampled_from(["agent", "human"]),
            st.integers(min_value=0, max_value=9000),
            st.floats(min_value=1, max_value=500, allow_nan=False, allow_infinity=False),
            st.floats(min_value=1, max_value=900, allow_nan=False, allow_infinity=False),
        ),
        max_size=14,
    ),
    since_ms=st.integers(min_value=-1000, max_value=130000),
)
def test_a_cursor_only_filters_what_is_returned(steps, since_ms):
    actions, now = [], 0
    for actor, gap, x, y in steps:
        now += gap
        actions.append(make_click(actor, now, x, y))
    log = log_with(actions)
    everything = log.get_human_actions()
    since = timestamp_at(since_ms)

    filtered = log.get_human_actions(since_timestamp=since)

    assert filtered.coordinate_scale_problem == everything.coordinate_scale_problem
    assert filtered.human_actions == [a for a in everything.human_actions if a.timestamp > since]
    assert filtered.mismatches == [m for m in everything.mismatches if m.human_click.timestamp > since]


# --- Requirement 2.1: scale_changed ---------------------------------------------

def problem(x, y=None, samples=3):
    return {"scale_x": x, "scale_y": x if y is None else y, "sample_size": samples, "spread_x": 0.0, "spread_y": 0.0}


def test_a_first_scale_problem_is_news():
    assert scale_changed(None, problem(1.5)) is True


def test_no_scale_problem_is_never_news():
    assert scale_changed(None, None) is False
    assert scale_changed(problem(1.5), None) is False


def test_the_same_scale_problem_is_not_news():
    assert scale_changed(problem(1.5), problem(1.5)) is False


def test_a_small_drift_is_not_news():
    assert scale_changed(problem(1.5), problem(1.5 * 1.04)) is False
    assert scale_changed(problem(1.5), problem(1.5 * 0.96)) is False


def test_just_under_and_just_over_five_percent():
    assert scale_changed(problem(2.0), problem(2.0 * 1.049)) is False
    assert scale_changed(problem(2.0), problem(2.0 * 1.051)) is True


def test_more_than_five_percent_in_either_axis_is_a_change():
    assert scale_changed(problem(1.5), problem(1.5 * 1.06)) is True
    assert scale_changed(problem(1.5), problem(1.5 * 0.94)) is True
    assert scale_changed(problem(1.5, 1.5), problem(1.5, 1.5 * 1.06)) is True
    assert scale_changed(problem(1.5, 1.5), problem(1.5 * 1.06, 1.5)) is True


def test_other_keys_are_ignored():
    assert scale_changed(problem(1.5, samples=3), problem(1.5, samples=9)) is False


# --- Requirement 2.2 and 2.3: the watcher ---------------------------------------

def payload(scale=None, actions=None, server_time="2026-05-15T14:30:00.000Z"):
    return {
        "human_actions": actions or [], "mismatches": [],
        "coordinate_scale_problem": scale, "server_time": server_time,
    }


class Scripted:
    """A fetch function that returns the payloads one after another."""

    def __init__(self, *payloads):
        self._payloads = list(payloads)

    def __call__(self, since):
        return self._payloads.pop(0)


def scale_lines(lines):
    return [line for line in lines if "consistent factor" in line]


def test_the_watcher_reports_the_scale_problem_when_the_third_correction_arrives(clock, http):
    watcher = _watcher(http)
    watcher.start()
    rounds = []
    for number, (agent, human) in enumerate([((150, 300), (100, 200)), ((225, 450), (150, 300)), ((300, 150), (200, 100))]):
        clock.advance(10)
        http.post("/agent-click", json={"x": agent[0], "y": agent[1], "coordinate_space": "device_points", "scale_factor": 1})
        clock.advance(1)
        human_click(http, *human)
        rounds.append(watcher.poll())

    assert scale_lines(rounds[0]) == [] and scale_lines(rounds[1]) == []
    [line] = scale_lines(rounds[2])
    assert "x1.50 horizontally" in line and "3 samples" in line


def test_the_watcher_does_not_repeat_a_scale_problem():
    watcher = Watcher(Scripted(payload(problem(1.5)), payload(problem(1.5)), payload(problem(1.5))))
    watcher.start()

    assert watcher.poll() == []
    assert watcher.poll() == []


def test_a_scale_problem_that_exists_when_the_watcher_starts_is_not_replayed():
    watcher = Watcher(Scripted(payload(problem(1.5)), payload(problem(1.5))))
    watcher.start()

    assert scale_lines(watcher.poll()) == []


def test_the_watcher_reports_a_new_scale_problem_and_a_changed_one():
    watcher = Watcher(Scripted(
        payload(None),
        payload(problem(1.5)),          # new
        payload(problem(1.5 * 1.03)),   # a small drift
        payload(problem(1.5 * 1.10)),   # changed
        payload(problem(1.5 * 1.10)),   # the same again
    ))
    watcher.start()

    assert len(scale_lines(watcher.poll())) == 1
    assert scale_lines(watcher.poll()) == []
    assert len(scale_lines(watcher.poll())) == 1
    assert scale_lines(watcher.poll()) == []


def test_the_watcher_reports_again_after_the_scale_problem_went_away():
    watcher = Watcher(Scripted(payload(None), payload(problem(1.5)), payload(None), payload(problem(1.5))))
    watcher.start()

    assert len(scale_lines(watcher.poll())) == 1
    assert watcher.poll() == []
    assert len(scale_lines(watcher.poll())) == 1


def test_describe_activity_still_describes_a_scale_problem_it_is_given():
    assert len(scale_lines(describe_activity(payload(problem(1.5))))) == 1


# --- Requirement 3: the state file ----------------------------------------------

def test_the_state_file_keeps_the_scale_when_the_cursor_is_saved(tmp_path):
    store = CursorStore("s1", str(tmp_path))
    store.save("2026-05-15T14:30:00.000Z")
    store.save_scale(problem(1.5, 1.6))
    store.save("2026-05-15T14:31:00.000Z")

    assert store.load() == "2026-05-15T14:31:00.000Z"
    assert store.load_scale() == {"scale_x": 1.5, "scale_y": 1.6}


def test_the_stored_scale_survives_a_new_process(tmp_path):
    CursorStore("s1", str(tmp_path)).save_scale(problem(1.5, 1.6, samples=7))

    assert CursorStore("s1", str(tmp_path)).load_scale() == {"scale_x": 1.5, "scale_y": 1.6}
    data = json.loads((tmp_path / "poltergeist-hook-s1.json").read_text())
    assert data["scale"] == {"scale_x": 1.5, "scale_y": 1.6}


def test_saving_none_removes_the_stored_scale_but_not_the_cursor(tmp_path):
    store = CursorStore("s1", str(tmp_path))
    store.save("2026-05-15T14:30:00.000Z")
    store.save_scale(problem(1.5))
    store.save_scale(None)

    assert store.load_scale() is None
    assert store.load() == "2026-05-15T14:30:00.000Z"


def test_a_state_file_from_before_this_change_has_no_scale(tmp_path):
    (tmp_path / "poltergeist-hook-s1.json").write_text(json.dumps({"cursor": "2026-05-15T14:30:00.000Z"}))
    store = CursorStore("s1", str(tmp_path))

    assert store.load() == "2026-05-15T14:30:00.000Z"
    assert store.load_scale() is None


def test_a_state_file_that_cannot_be_written_never_raises(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    store = CursorStore("s1", str(blocker))

    store.save_scale(problem(1.5))
    store.save("2026-05-15T14:30:00.000Z")

    assert store.load_scale() is None


# --- Requirement 2.4: the hook ------------------------------------------------------

class ScriptedServer(Server):
    def __init__(self, *payloads):
        super().__init__("http://scripted")
        self._payloads = list(payloads)

    def record_agent(self, body):
        pass

    def human_actions(self, since):
        return self._payloads.pop(0)


SHOT = {"session_id": "s1", "tool_name": "mcp__Claude_Code_iOS_Simulator__control", "tool_input": {"action": "screenshot"}}


def test_the_hook_tells_the_agent_when_the_third_correction_arrives(clock, http, tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = HttpServer(http)
    handle_event(event({"action": "screenshot"}), hook, cursor)  # the first call only starts the clock
    contexts = []
    for agent, human in [((150, 300), (100, 200)), ((225, 450), (150, 300)), ((300, 150), (200, 100))]:
        clock.advance(10)
        handle_event(event({"action": "tap", "x": agent[0], "y": agent[1]}), hook, cursor)
        clock.advance(1)
        human_click(http, *human)
        contexts.append(handle_event(event({"action": "screenshot"}), hook, cursor))

    assert "consistent factor" not in (contexts[0] or "")
    assert "consistent factor" not in (contexts[1] or "")
    assert "x1.50 horizontally" in contexts[2]
    assert "3 samples" in contexts[2]
    clock.advance(1)
    assert handle_event(event({"action": "screenshot"}), hook, cursor) is None


def test_the_first_call_remembers_a_scale_problem_that_already_exists_and_says_nothing(tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = ScriptedServer(payload(problem(1.5)), payload(problem(1.5)))

    assert handle_event(SHOT, hook, cursor) is None
    assert cursor.load_scale() == {"scale_x": 1.5, "scale_y": 1.5}
    assert handle_event(SHOT, hook, cursor) is None


def test_the_hook_speaks_again_only_when_the_scale_problem_changes(tmp_path):
    cursor = CursorStore("s1", str(tmp_path))
    hook = ScriptedServer(
        payload(None),                  # first call
        payload(problem(1.5)),          # new
        payload(problem(1.5)),          # the same
        payload(problem(1.5 * 1.10)),   # changed
        payload(problem(1.5 * 1.10)),   # the same again
        payload(None),                  # gone
        payload(problem(1.5)),          # back
    )

    assert handle_event(SHOT, hook, cursor) is None
    assert "x1.50 horizontally" in handle_event(SHOT, hook, cursor)
    assert handle_event(SHOT, hook, cursor) is None
    assert "x1.65 horizontally" in handle_event(SHOT, hook, cursor)
    assert handle_event(SHOT, hook, cursor) is None
    assert handle_event(SHOT, hook, cursor) is None
    assert cursor.load_scale() is None
    assert "x1.50 horizontally" in handle_event(SHOT, hook, cursor)
