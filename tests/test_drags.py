"""Drags: a swipe or any press-move-release is recorded with a start and an end point."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from helpers import make_click
from poltergeist import server
from poltergeist.action_log import ActionLog, ClickAction
from poltergeist.detection import detect_mismatches


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


def drag_body(**overrides):
    body = {
        "x": 215, "y": 800, "end_x": 215, "end_y": 300,
        "coordinate_space": "device_points", "scale_factor": 1,
    }
    body.update(overrides)
    return body


# --- ActionLog --------------------------------------------------------------

def test_a_click_has_kind_click_and_no_end_point():
    action = ActionLog().record_human_click(10, 20, "device_points", 1.0)
    assert action.kind == "click"
    assert action.end_x is None and action.end_y is None


def test_a_human_drag_records_both_ends():
    action = ActionLog().record_human_drag(215, 800, 215, 300, "device_points", 1.0)
    assert action.kind == "drag"
    assert action.actor == "human"
    assert (action.normalized_x, action.normalized_y) == (215, 800)
    assert (action.end_x, action.end_y) == (215, 300)


def test_an_agent_drag_is_recorded_as_the_agent():
    action = ActionLog().record_agent_drag(1, 2, 3, 4, "device_points", 1.0)
    assert action.actor == "agent"
    assert action.kind == "drag"


def test_the_end_point_is_normalized_with_the_same_scale_factor():
    action = ActionLog().record_human_drag(300, 2400, 300, 900, "screenshot_pixels", 3.0)
    assert (action.normalized_x, action.normalized_y) == (100, 800)
    assert (action.end_x, action.end_y) == (100, 300)
    assert (action.raw_x, action.raw_y) == (300, 2400)


def test_non_finite_end_points_are_rejected():
    log = ActionLog()
    with pytest.raises(ValueError, match="end_x and end_y must be finite"):
        log.record_human_drag(1, 2, float("nan"), 4, "device_points", 1.0)
    assert log._actions == []


def test_a_drag_keeps_its_ui_element_role():
    from poltergeist.action_log import UIElement

    action = ActionLog().record_human_drag(
        1, 2, 3, 4, "device_points", 1.0, UIElement(role="slider", label="Volume")
    )
    assert action.ui_element.role == "slider"


# --- Queries ----------------------------------------------------------------

def test_human_drags_are_listed_with_the_clicks_oldest_first(clock):
    log = server.action_log
    log.record_human_click(10, 10, "device_points", 1.0)
    clock.advance(1)
    log.record_human_drag(100, 700, 100, 200, "device_points", 1.0)
    clock.advance(1)
    log.record_human_click(50, 50, "device_points", 1.0)

    kinds = [a.kind for a in log.get_human_actions().human_actions]

    assert kinds == ["click", "drag", "click"]


def test_agent_drags_are_not_human_actions(clock):
    server.action_log.record_agent_drag(100, 700, 100, 200, "device_points", 1.0)
    assert server.action_log.get_human_actions().human_actions == []


def test_the_mcp_result_includes_kind_and_the_end_point(clock):
    server.action_log.record_human_drag(215, 800, 215, 300, "device_points", 1.0)

    result = server.get_human_actions()

    [action] = result["human_actions"]
    assert action["kind"] == "drag"
    assert (action["end_x"], action["end_y"]) == (215, 300)


# --- Mismatches only pair clicks ---------------------------------------------

def _drag(actor, ms, x=0.0, y=0.0):
    base = make_click(actor, ms, x, y)
    return ClickAction(
        timestamp=base.timestamp, actor=actor, normalized_x=x, normalized_y=y,
        raw_x=x, raw_y=y, coordinate_space="device_points", scale_factor=1.0,
        kind="drag", end_x=x + 50, end_y=y + 50,
    )


def test_a_human_drag_after_an_agent_click_is_not_a_mismatch():
    log = [make_click("agent", 0, 100, 100), _drag("human", 1000, 100, 100)]
    assert detect_mismatches(log) == []


def test_an_agent_drag_is_never_paired_with_a_human_click():
    log = [_drag("agent", 0, 100, 100), make_click("human", 1000, 110, 105)]
    assert detect_mismatches(log) == []


def test_a_drag_in_between_does_not_stop_a_click_pairing():
    log = [
        make_click("agent", 0, 100, 100),
        _drag("human", 500, 300, 300),
        make_click("human", 1000, 110, 105),
    ]
    [mismatch] = detect_mismatches(log)
    assert mismatch.human_click.kind == "click"


# --- HTTP -------------------------------------------------------------------

def test_posting_end_coordinates_records_a_human_drag(clock, http):
    response = http.post("/human-click", json=drag_body())

    assert response.status_code == 200
    assert response.json()["kind"] == "drag"
    assert response.json()["actor"] == "human"
    [action] = server.action_log._actions
    assert (action.end_x, action.end_y) == (215, 300)


def test_posting_to_agent_click_with_end_coordinates_records_an_agent_drag(clock, http):
    response = http.post("/agent-click", json=drag_body())

    assert response.json()["kind"] == "drag"
    assert server.action_log._actions[0].actor == "agent"


def test_a_plain_click_reports_kind_click(clock, http):
    body = drag_body()
    del body["end_x"], body["end_y"]
    response = http.post("/human-click", json=body)

    assert response.json()["kind"] == "click"


def test_only_one_end_coordinate_is_rejected(clock, http):
    body = drag_body()
    del body["end_y"]
    response = http.post("/human-click", json=body)

    assert response.status_code == 400
    assert "end_x and end_y must be given together" in response.json()["error"]
    assert server.action_log._actions == []


def test_a_non_numeric_end_coordinate_is_rejected(clock, http):
    response = http.post("/human-click", json=drag_body(end_x="up"))

    assert response.status_code == 400
    assert "Invalid field type" in response.json()["error"]


def test_end_coordinates_use_the_request_scale_factor(clock, http):
    http.post("/human-click", json=drag_body(
        x=300, y=2400, end_x=300, end_y=900, coordinate_space="screenshot_pixels", scale_factor=3,
    ))
    [action] = server.action_log._actions
    assert (action.normalized_y, action.end_y) == (800, 300)


def test_the_agent_sees_a_human_drag_through_the_tool(clock, http):
    http.post("/agent-click", json={"x": 5, "y": 5, "coordinate_space": "device_points", "scale_factor": 1})
    clock.advance(1)
    http.post("/human-click", json=drag_body())

    result = server.get_human_actions()

    assert [a["kind"] for a in result["human_actions"]] == ["drag"]
    assert result["mismatches"] == []
