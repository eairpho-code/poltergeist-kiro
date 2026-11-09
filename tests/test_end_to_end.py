"""End-to-end workflows (task 14).

An agent records clicks through the MCP tools, a human click arrives through the
HTTP endpoint, and the agent reads the result back through get_human_actions.
Time is controlled by a fake clock so "waiting two seconds" costs nothing.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from mcp import Client
from starlette.testclient import TestClient

from poltergeist import server
from poltergeist.action_log import ActionLog


class FakeClock:
    """A clock the test moves by hand."""

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


def call_tool(name, arguments=None):
    """Call an MCP tool through the real protocol (in-memory transport)."""
    async def run():
        async with Client(server.mcp) as client:
            return await client.call_tool(name, arguments or {})

    result = asyncio.run(run())
    assert not result.is_error, result.content[0].text
    return json.loads(result.content[0].text)


def agent_click(x, y, coordinate_space="device_points", scale_factor=1.0):
    return call_tool("record_agent_click", {
        "x": x, "y": y,
        "coordinate_space": coordinate_space, "scale_factor": scale_factor,
    })


def human_click(http, x, y, coordinate_space="device_points", scale_factor=1.0):
    response = http.post("/human-click", json={
        "x": x, "y": y,
        "coordinate_space": coordinate_space, "scale_factor": scale_factor,
    })
    assert response.status_code == 200, response.text
    return response.json()


# --- 14.1 -------------------------------------------------------------------

def test_agent_click_then_human_correction_is_reported_as_a_mismatch(clock, http):
    agent_click(100, 100)
    clock.advance(2)
    human_click(http, 110, 105)

    result = call_tool("get_human_actions")

    assert len(result["human_actions"]) == 1
    assert len(result["mismatches"]) == 1
    mismatch = result["mismatches"][0]
    assert mismatch["offset_x"] == 10
    assert mismatch["offset_y"] == 5
    assert mismatch["agent_click"]["actor"] == "agent"
    assert mismatch["human_click"]["actor"] == "human"
    assert result["coordinate_scale_problem"] is None


def test_human_click_after_the_five_second_window_is_not_a_mismatch(clock, http):
    agent_click(100, 100)
    clock.advance(6)
    human_click(http, 110, 105)

    result = call_tool("get_human_actions")

    assert len(result["human_actions"]) == 1
    assert result["mismatches"] == []


def test_agent_and_human_clicks_in_different_coordinate_spaces_still_match(clock, http):
    # The agent measured on a 3x screenshot; the human clicked in device points.
    agent_click(300, 600, coordinate_space="screenshot_pixels", scale_factor=3.0)
    clock.advance(1)
    human_click(http, 100, 200)

    result = call_tool("get_human_actions")

    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["offset_x"] == 0
    assert result["mismatches"][0]["offset_y"] == 0
    assert result["mismatches"][0]["agent_click"]["raw_x"] == 300


# --- 14.2 -------------------------------------------------------------------

def test_systematic_two_x_error_is_flagged_as_a_scale_problem(clock, http):
    human_positions = [(100, 150), (220, 80), (60, 300), (180, 210), (140, 90)]
    for human_x, human_y in human_positions:
        # The agent's coordinates are twice what the human then clicks.
        agent_click(human_x * 2, human_y * 2)
        clock.advance(1)
        human_click(http, human_x, human_y)
        clock.advance(10)

    result = call_tool("get_human_actions")

    assert len(result["mismatches"]) == 5
    problem = result["coordinate_scale_problem"]
    assert problem is not None
    assert problem["sample_size"] == 5
    assert problem["scale_x"] == pytest.approx(2.0)
    assert problem["scale_y"] == pytest.approx(2.0)
    assert problem["spread_x"] < 0.10
    assert problem["spread_y"] < 0.10


def test_scattered_misses_are_not_flagged_as_a_scale_problem(clock, http):
    pairs = [((100, 100), (103, 98)), ((300, 200), (150, 400)), ((50, 500), (55, 260))]
    for (agent_x, agent_y), (human_x, human_y) in pairs:
        agent_click(agent_x, agent_y)
        clock.advance(1)
        human_click(http, human_x, human_y)
        clock.advance(10)

    result = call_tool("get_human_actions")

    assert len(result["mismatches"]) == 3
    assert result["coordinate_scale_problem"] is None


# --- Whole agent loop -------------------------------------------------------

def test_since_timestamp_lets_the_agent_poll_only_for_new_human_actions(clock, http):
    agent_click(10, 10)
    clock.advance(1)
    first = human_click(http, 12, 12)
    clock.advance(10)

    agent_click(200, 200)
    clock.advance(1)
    second = human_click(http, 205, 195)

    only_new = call_tool("get_human_actions", {"since_timestamp": first["timestamp"]})

    assert [a["timestamp"] for a in only_new["human_actions"]] == [second["timestamp"]]
    assert len(only_new["mismatches"]) == 1
    assert only_new["mismatches"][0]["offset_x"] == 5


def test_clear_then_query_starts_from_an_empty_log(clock, http):
    agent_click(10, 10)
    clock.advance(1)
    human_click(http, 12, 12)

    assert call_tool("clear_action_log") == {"removed_count": 2}

    result = call_tool("get_human_actions")
    assert result["human_actions"] == []
    assert result["mismatches"] == []
