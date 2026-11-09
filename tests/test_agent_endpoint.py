"""Tests for POST /agent-click, the HTTP door for an agent that moves the real mouse."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from poltergeist import server
from poltergeist.action_log import ActionLog

VALID = {"x": 100, "y": 200, "coordinate_space": "device_points", "scale_factor": 1}


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


def test_valid_agent_click_is_recorded_as_an_agent_action(clock, http):
    response = http.post("/agent-click", json=VALID)

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    assert response.json()["actor"] == "agent"
    assert response.json()["timestamp"] == "2026-05-15T14:30:00.000Z"
    [recorded] = server.action_log._actions
    assert recorded.actor == "agent"
    assert (recorded.normalized_x, recorded.normalized_y) == (100.0, 200.0)


def test_agent_click_keeps_the_ui_element(clock, http):
    body = {**VALID, "ui_element": {"role": "button", "label": "Save"}}
    http.post("/agent-click", json=body)

    [recorded] = server.action_log._actions
    assert recorded.ui_element.role == "button"
    assert recorded.ui_element.label == "Save"


def test_agent_click_honours_the_scale_factor(clock, http):
    http.post("/agent-click", json={**VALID, "x": 300, "y": 600, "scale_factor": 3})

    [recorded] = server.action_log._actions
    assert (recorded.normalized_x, recorded.normalized_y) == (100.0, 200.0)
    assert recorded.raw_x == 300


@pytest.mark.parametrize("body, message", [
    ({**VALID, "coordinate_space": "inches"}, "Invalid coordinate_space"),
    ({**VALID, "scale_factor": 0}, "scale_factor must be greater than 0"),
    ({"x": 1}, "Missing required fields"),
    ({**VALID, "x": "left"}, "Invalid field type"),
    ({**VALID, "ui_element": "button"}, "ui_element must be an object"),
])
def test_bad_agent_click_is_a_400_with_the_reason(clock, http, body, message):
    response = http.post("/agent-click", json=body)

    assert response.status_code == 400
    assert message in response.json()["error"]
    assert server.action_log._actions == []


def test_invalid_json_and_non_object_bodies_are_400(clock, http):
    assert http.post("/agent-click", content=b"not json").status_code == 400
    assert http.post("/agent-click", json=[1, 2]).status_code == 400


def test_a_human_correction_after_an_http_agent_click_is_a_mismatch(clock, http):
    # The same flow the click observer produces when an AI moves the real mouse
    # and the person then steps in.
    http.post("/agent-click", json={**VALID, "x": 110, "y": 190})
    clock.advance(2)
    http.post("/human-click", json={**VALID, "x": 115, "y": 180})

    response = server.action_log.get_human_actions()

    assert len(response.human_actions) == 1
    assert len(response.mismatches) == 1
    assert (response.mismatches[0].offset_x, response.mismatches[0].offset_y) == (5.0, -10.0)


def test_agent_clicks_never_show_up_as_human_actions(clock, http):
    http.post("/agent-click", json=VALID)
    http.post("/agent-click", json={**VALID, "x": 5})

    response = server.action_log.get_human_actions()

    assert response.human_actions == []
    assert response.mismatches == []


def test_agent_endpoint_logs_the_click(clock, http, caplog):
    import logging

    logger = logging.getLogger("poltergeist")
    previous = logger.propagate
    logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="poltergeist"):
            http.post("/agent-click", json=VALID)
    finally:
        logger.propagate = previous

    assert any("/agent-click recorded" in r.getMessage() for r in caplog.records)
