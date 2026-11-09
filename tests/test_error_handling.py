"""Tests for validation errors and logging (task 13)."""

import io
import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

from poltergeist import server
from poltergeist.action_log import ActionLog, UIElement
from poltergeist.logging_config import LEVEL_ENV_VAR, configure_logging


class ListHandler(logging.Handler):
    """Collects log records so tests can inspect level and message."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def at(self, level):
        return [r.getMessage() for r in self.records if r.levelno == level]


@pytest.fixture
def log_records():
    logger = logging.getLogger("poltergeist")
    handler = ListHandler()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(previous_level)


@pytest.fixture(autouse=True)
def fresh_action_log(monkeypatch):
    """Every test gets its own empty global log and no redaction."""
    monkeypatch.delenv("POLTERGEIST_REDACT_UI_LABELS", raising=False)
    monkeypatch.setattr(server, "action_log", ActionLog())
    return server.action_log


# --- Validation error messages ---------------------------------------------

def test_invalid_coordinate_space_message():
    with pytest.raises(ToolError, match="Invalid coordinate_space. Must be one of"):
        server.record_agent_click(1.0, 1.0, "inches", 1.0)


def test_zero_scale_factor_message():
    with pytest.raises(ToolError, match="scale_factor must be greater than 0"):
        server.record_agent_click(1.0, 1.0, "device_points", 0.0)


def test_negative_and_non_finite_scale_factors_are_rejected():
    for bad in (-2.0, float("nan"), float("inf")):
        with pytest.raises(ToolError, match="scale_factor must be greater than 0"):
            server.record_agent_click(1.0, 1.0, "device_points", bad)


def test_non_finite_coordinates_are_rejected():
    with pytest.raises(ToolError, match="x and y must be finite"):
        server.record_agent_click(float("nan"), 1.0, "device_points", 1.0)


def test_invalid_timestamp_message_for_get_and_clear():
    with pytest.raises(ToolError, match="timestamp must be UTC ISO 8601"):
        server.get_human_actions("not-a-timestamp")
    with pytest.raises(ToolError, match="timestamp must be UTC ISO 8601"):
        server.clear_action_log("2026-05-15")  # no time zone marker


def test_a_rejected_click_is_not_recorded(fresh_action_log):
    with pytest.raises(ToolError):
        server.record_agent_click(1.0, 1.0, "inches", 1.0)
    assert fresh_action_log._actions == []


# --- Label truncation -------------------------------------------------------

def test_label_is_truncated_to_50_characters(fresh_action_log):
    action = fresh_action_log.record_agent_click(
        1.0, 1.0, "device_points", 1.0, UIElement(role="button", label="x" * 80)
    )
    assert action.ui_element.label == "x" * 50


def test_truncation_logs_a_warning_without_the_label_text(fresh_action_log, log_records):
    secret = "secret-" + "y" * 80
    fresh_action_log.record_agent_click(
        1.0, 1.0, "device_points", 1.0, UIElement(role="button", label=secret)
    )
    warnings = log_records.at(logging.WARNING)
    assert len(warnings) == 1
    assert "truncated" in warnings[0]
    assert "secret" not in warnings[0]


def test_short_label_is_kept_and_not_warned_about(fresh_action_log, log_records):
    action = fresh_action_log.record_agent_click(
        1.0, 1.0, "device_points", 1.0, UIElement(role="button", label="Submit")
    )
    assert action.ui_element.label == "Submit"
    assert log_records.at(logging.WARNING) == []


def test_label_of_exactly_50_characters_is_kept(fresh_action_log, log_records):
    action = fresh_action_log.record_agent_click(
        1.0, 1.0, "device_points", 1.0, UIElement(role="button", label="z" * 50)
    )
    assert action.ui_element.label == "z" * 50
    assert log_records.at(logging.WARNING) == []


# --- Logging behavior -------------------------------------------------------

def test_tool_calls_are_logged_at_info_without_labels(log_records):
    server.record_agent_click(5.0, 6.0, "device_points", 1.0, "button", "Pay now")
    server.get_human_actions()
    server.clear_action_log()
    messages = log_records.at(logging.INFO)
    assert any(m.startswith("record_agent_click") for m in messages)
    assert any(m.startswith("get_human_actions") for m in messages)
    assert any(m.startswith("clear_action_log") for m in messages)
    assert not any("Pay now" in r.getMessage() for r in log_records.records)


def test_validation_failure_is_logged_as_warning(log_records):
    with pytest.raises(ToolError):
        server.record_agent_click(1.0, 1.0, "inches", 1.0)
    assert any("rejected" in m for m in log_records.at(logging.WARNING))


def test_human_click_endpoint_logs_success_and_rejection(log_records):
    with TestClient(server.mcp.streamable_http_app()) as client:
        ok = client.post("/human-click", json={
            "x": 1, "y": 2, "coordinate_space": "device_points", "scale_factor": 1,
        })
        bad = client.post("/human-click", json={
            "x": 1, "y": 2, "coordinate_space": "inches", "scale_factor": 1,
        })
    assert ok.status_code == 200
    assert bad.status_code == 400
    assert any(m.startswith("/human-click recorded") for m in log_records.at(logging.INFO))
    assert any("Invalid coordinate_space" in m for m in log_records.at(logging.WARNING))


def test_runtime_exception_is_logged_as_error_and_returns_500(monkeypatch, log_records):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(server.action_log, "record_human_click", explode)
    with TestClient(server.mcp.streamable_http_app()) as client:
        response = client.post("/human-click", json={
            "x": 1, "y": 2, "coordinate_space": "device_points", "scale_factor": 1,
        })
    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert any("failed while recording" in m for m in log_records.at(logging.ERROR))


def test_non_object_json_body_is_a_bad_request():
    with TestClient(server.mcp.streamable_http_app()) as client:
        response = client.post("/human-click", json=[1, 2, 3])
    assert response.status_code == 400


# --- configure_logging ------------------------------------------------------

@pytest.fixture
def restore_poltergeist_logger():
    logger = logging.getLogger("poltergeist")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield logger
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_default_level_is_info(monkeypatch, restore_poltergeist_logger):
    monkeypatch.delenv(LEVEL_ENV_VAR, raising=False)
    logger = configure_logging(stream=io.StringIO())
    assert logger.level == logging.INFO


def test_level_comes_from_environment(monkeypatch, restore_poltergeist_logger):
    monkeypatch.setenv(LEVEL_ENV_VAR, "warning")
    assert configure_logging(stream=io.StringIO()).level == logging.WARNING


def test_unknown_level_falls_back_to_info_with_a_warning(monkeypatch, restore_poltergeist_logger):
    monkeypatch.setenv(LEVEL_ENV_VAR, "LOUD")
    stream = io.StringIO()
    logger = configure_logging(stream=stream)
    assert logger.level == logging.INFO
    assert "Unknown POLTERGEIST_LOG_LEVEL" in stream.getvalue()


def test_info_is_hidden_when_level_is_warning(monkeypatch, restore_poltergeist_logger):
    monkeypatch.setenv(LEVEL_ENV_VAR, "WARNING")
    stream = io.StringIO()
    logger = configure_logging(stream=stream)
    logger.getChild("test").info("quiet")
    logger.getChild("test").warning("loud")
    assert "quiet" not in stream.getvalue()
    assert "loud" in stream.getvalue()


def test_logs_go_to_stderr_never_stdout(monkeypatch, restore_poltergeist_logger, capsys):
    monkeypatch.delenv(LEVEL_ENV_VAR, raising=False)
    logger = configure_logging()
    logger.getChild("test").info("to stderr")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "to stderr" in captured.err


def test_configuring_twice_does_not_duplicate_lines(monkeypatch, restore_poltergeist_logger):
    monkeypatch.delenv(LEVEL_ENV_VAR, raising=False)
    first, second = io.StringIO(), io.StringIO()
    configure_logging(stream=first)
    logger = configure_logging(stream=second)
    logger.getChild("test").info("once")
    assert first.getvalue() == ""
    assert second.getvalue().count("once") == 1
