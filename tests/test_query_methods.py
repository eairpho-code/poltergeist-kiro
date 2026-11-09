"""Unit tests for ActionLog query methods (get_human_actions and clear)."""

import pytest
from datetime import datetime, timedelta, timezone

from poltergeist.action_log import ActionLog, UIElement
from tests.helpers import BASE_TIME, timestamp_at, make_click


def fixed_clock(ms: int):
    """Return a clock function that returns BASE_TIME + ms milliseconds."""
    def clock():
        return BASE_TIME + timedelta(milliseconds=ms)
    return clock


def test_get_human_actions_filters_by_timestamp():
    """Test that get_human_actions filters human clicks by timestamp correctly."""
    log = ActionLog(clock=fixed_clock(0))
    
    # Record actions at different times
    log._actions = [
        make_click("agent", 1000, 100, 100),
        make_click("human", 2000, 110, 105),
        make_click("agent", 3000, 200, 200),
        make_click("human", 4000, 210, 205),
    ]
    
    # Query with since_timestamp at 3000ms
    result = log.get_human_actions(since_timestamp=timestamp_at(3000))
    
    # Should only return human clicks after 3000ms (exclusive)
    assert len(result.human_actions) == 1
    assert result.human_actions[0].timestamp == timestamp_at(4000)


def test_get_human_actions_with_no_timestamp_returns_all():
    """Test that get_human_actions with no timestamp returns all human actions."""
    log = ActionLog(clock=fixed_clock(0))
    
    log._actions = [
        make_click("agent", 1000, 100, 100),
        make_click("human", 2000, 110, 105),
        make_click("agent", 3000, 200, 200),
        make_click("human", 4000, 210, 205),
    ]
    
    result = log.get_human_actions()
    
    assert len(result.human_actions) == 2
    assert result.human_actions[0].timestamp == timestamp_at(2000)
    assert result.human_actions[1].timestamp == timestamp_at(4000)


def test_get_human_actions_chronological_order():
    """Test that get_human_actions returns human actions in chronological order (oldest first)."""
    log = ActionLog(clock=fixed_clock(0))
    
    log._actions = [
        make_click("human", 5000, 300, 300),
        make_click("human", 2000, 110, 105),
        make_click("human", 4000, 210, 205),
    ]
    
    result = log.get_human_actions()
    
    # Should be in chronological order (oldest first)
    assert len(result.human_actions) == 3
    assert result.human_actions[0].timestamp == timestamp_at(2000)
    assert result.human_actions[1].timestamp == timestamp_at(4000)
    assert result.human_actions[2].timestamp == timestamp_at(5000)


def test_get_human_actions_invalid_timestamp_format():
    """Test that invalid timestamp format raises ValueError."""
    log = ActionLog()
    
    with pytest.raises(ValueError, match="timestamp must be UTC ISO 8601"):
        log.get_human_actions(since_timestamp="invalid-timestamp")


def test_clear_with_timestamp_removes_correct_actions():
    """Test that clear with timestamp removes actions before timestamp (exclusive)."""
    log = ActionLog(clock=fixed_clock(0))
    
    log._actions = [
        make_click("agent", 1000, 100, 100),
        make_click("human", 2000, 110, 105),
        make_click("agent", 3000, 200, 200),
        make_click("human", 4000, 210, 205),
    ]
    
    # Clear actions before 3000ms (exclusive)
    count = log.clear(before_timestamp=timestamp_at(3000))
    
    assert count == 2  # Two actions removed
    assert len(log._actions) == 2
    assert log._actions[0].timestamp == timestamp_at(3000)
    assert log._actions[1].timestamp == timestamp_at(4000)


def test_clear_without_timestamp_removes_all():
    """Test that clear without timestamp removes all actions."""
    log = ActionLog(clock=fixed_clock(0))
    
    log._actions = [
        make_click("agent", 1000, 100, 100),
        make_click("human", 2000, 110, 105),
        make_click("agent", 3000, 200, 200),
    ]
    
    count = log.clear()
    
    assert count == 3
    assert len(log._actions) == 0


def test_clear_on_empty_log_returns_zero():
    """Test that clear on empty log returns 0."""
    log = ActionLog()
    
    count = log.clear()
    
    assert count == 0
    assert len(log._actions) == 0


def test_clear_invalid_timestamp_format():
    """Test that clear with invalid timestamp format raises ValueError."""
    log = ActionLog()
    
    with pytest.raises(ValueError, match="timestamp must be UTC ISO 8601"):
        log.clear(before_timestamp="invalid-timestamp")
