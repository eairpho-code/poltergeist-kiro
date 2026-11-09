"""Unit tests for ActionLog class."""

import os
from datetime import datetime, timezone, timedelta

import pytest

from poltergeist.action_log import ActionLog, UIElement, ClickAction


class TestActionLogBasics:
    """Test basic ActionLog initialization and recording."""
    
    def test_initialization(self):
        """ActionLog initializes with empty list."""
        log = ActionLog()
        assert log._actions == []
    
    def test_custom_clock(self):
        """ActionLog accepts custom clock for timestamp injection."""
        fixed_time = datetime(2026, 5, 15, 14, 30, 45, 123000, tzinfo=timezone.utc)
        log = ActionLog(clock=lambda: fixed_time)
        
        log.record_agent_click(100, 200, "device_points", 1.0)
        
        assert len(log._actions) == 1
        assert log._actions[0].timestamp == "2026-05-15T14:30:45.123Z"


class TestAgentClickRecording:
    """Test record_agent_click method."""
    
    def test_agent_click_creates_action(self):
        """Agent click recording creates ClickAction with actor='agent'."""
        log = ActionLog()
        log.record_agent_click(400, 600, "screen_pixels", 2.0)
        
        assert len(log._actions) == 1
        action = log._actions[0]
        assert action.actor == "agent"
        assert action.normalized_x == 200.0
        assert action.normalized_y == 300.0
        assert action.raw_x == 400.0
        assert action.raw_y == 600.0
        assert action.coordinate_space == "screen_pixels"
        assert action.scale_factor == 2.0
    
    def test_agent_click_with_ui_element(self):
        """Agent click recording with UI element stores element."""
        log = ActionLog()
        ui_element = UIElement(role="button", label="Submit")
        log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
        
        action = log._actions[0]
        assert action.ui_element is not None
        assert action.ui_element.role == "button"
        assert action.ui_element.label == "Submit"
    
    def test_agent_click_timestamp_format(self):
        """Agent click timestamp is ISO 8601 with milliseconds and trailing Z."""
        log = ActionLog()
        log.record_agent_click(100, 200, "device_points", 1.0)
        
        timestamp = log._actions[0].timestamp
        # Should end with Z
        assert timestamp.endswith("Z")
        # Should parse as valid ISO 8601
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed.tzinfo == timezone.utc
        # Should have milliseconds (format: YYYY-MM-DDTHH:MM:SS.sssZ)
        assert "." in timestamp


class TestHumanClickRecording:
    """Test record_human_click method."""
    
    def test_human_click_creates_action(self):
        """Human click recording creates ClickAction with actor='human'."""
        log = ActionLog()
        log.record_human_click(400, 600, "screen_pixels", 2.0)
        
        assert len(log._actions) == 1
        action = log._actions[0]
        assert action.actor == "human"
        assert action.normalized_x == 200.0
        assert action.normalized_y == 300.0
    
    def test_human_click_with_ui_element(self):
        """Human click recording with UI element stores element."""
        log = ActionLog()
        ui_element = UIElement(role="link", label="Home")
        log.record_human_click(100, 200, "device_points", 1.0, ui_element)
        
        action = log._actions[0]
        assert action.ui_element is not None
        assert action.ui_element.role == "link"
        assert action.ui_element.label == "Home"


class TestChronologicalOrder:
    """Test that actions preserve chronological order."""
    
    def test_chronological_order_preserved(self):
        """Multiple clicks are stored in chronological order."""
        fixed_time = datetime(2026, 5, 15, 14, 0, 0, tzinfo=timezone.utc)
        
        def clock():
            nonlocal fixed_time
            result = fixed_time
            fixed_time = fixed_time + timedelta(seconds=1)
            return result
        
        log = ActionLog(clock=clock)
        
        log.record_agent_click(100, 100, "device_points", 1.0)
        log.record_human_click(200, 200, "device_points", 1.0)
        log.record_agent_click(300, 300, "device_points", 1.0)
        
        assert len(log._actions) == 3
        assert log._actions[0].actor == "agent"
        assert log._actions[0].normalized_x == 100.0
        assert log._actions[1].actor == "human"
        assert log._actions[1].normalized_x == 200.0
        assert log._actions[2].actor == "agent"
        assert log._actions[2].normalized_x == 300.0


class TestUIElementRedaction:
    """Test UI element redaction enabled/disabled."""
    
    def test_redaction_disabled_keeps_label(self):
        """When redaction is disabled, label is preserved."""
        # Ensure environment variable is not set
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        if old_value:
            del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
        
        try:
            log = ActionLog()
            ui_element = UIElement(role="button", label="Click Me")
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            action = log._actions[0]
            assert action.ui_element.role == "button"
            assert action.ui_element.label == "Click Me"
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
    
    def test_redaction_enabled_removes_label(self):
        """When redaction is enabled, label is set to None."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        os.environ["POLTERGEIST_REDACT_UI_LABELS"] = "1"
        
        try:
            log = ActionLog()
            ui_element = UIElement(role="button", label="Sensitive Info")
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            action = log._actions[0]
            assert action.ui_element.role == "button"
            assert action.ui_element.label is None
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
            else:
                del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
    
    def test_redaction_true_string(self):
        """Redaction works with 'true' string."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        os.environ["POLTERGEIST_REDACT_UI_LABELS"] = "true"
        
        try:
            log = ActionLog()
            ui_element = UIElement(role="button", label="Test")
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            assert log._actions[0].ui_element.label is None
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
            else:
                del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
    
    def test_redaction_yes_string(self):
        """Redaction works with 'yes' string."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        os.environ["POLTERGEIST_REDACT_UI_LABELS"] = "Yes"
        
        try:
            log = ActionLog()
            ui_element = UIElement(role="button", label="Test")
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            assert log._actions[0].ui_element.label is None
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
            else:
                del os.environ["POLTERGEIST_REDACT_UI_LABELS"]


class TestLabelTruncation:
    """Test label truncation to 50 characters."""
    
    def test_label_truncated_to_50_chars(self):
        """Label longer than 50 characters is truncated."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        if old_value:
            del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
        
        try:
            log = ActionLog()
            long_label = "a" * 100  # 100 characters
            ui_element = UIElement(role="button", label=long_label)
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            action = log._actions[0]
            assert len(action.ui_element.label) == 50
            assert action.ui_element.label == "a" * 50
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
    
    def test_label_exactly_50_chars_not_truncated(self):
        """Label with exactly 50 characters is not truncated."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        if old_value:
            del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
        
        try:
            log = ActionLog()
            label_50 = "a" * 50
            ui_element = UIElement(role="button", label=label_50)
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            action = log._actions[0]
            assert action.ui_element.label == label_50
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value
    
    def test_label_under_50_chars_not_truncated(self):
        """Label shorter than 50 characters is not modified."""
        old_value = os.environ.get("POLTERGEIST_REDACT_UI_LABELS")
        if old_value:
            del os.environ["POLTERGEIST_REDACT_UI_LABELS"]
        
        try:
            log = ActionLog()
            short_label = "Submit"
            ui_element = UIElement(role="button", label=short_label)
            log.record_agent_click(100, 200, "device_points", 1.0, ui_element)
            
            action = log._actions[0]
            assert action.ui_element.label == "Submit"
        finally:
            if old_value:
                os.environ["POLTERGEIST_REDACT_UI_LABELS"] = old_value


class TestValidation:
    """Test validation of inputs."""
    
    def test_invalid_coordinate_space_raises(self):
        """Invalid coordinate space raises ValueError."""
        log = ActionLog()
        
        with pytest.raises(ValueError, match="Invalid coordinate_space"):
            log.record_agent_click(100, 200, "invalid_space", 1.0)
    
    def test_zero_scale_factor_raises(self):
        """Scale factor of 0 raises ValueError."""
        log = ActionLog()
        
        with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
            log.record_agent_click(100, 200, "device_points", 0.0)
    
    def test_negative_scale_factor_raises(self):
        """Negative scale factor raises ValueError."""
        log = ActionLog()
        
        with pytest.raises(ValueError, match="scale_factor must be greater than 0"):
            log.record_agent_click(100, 200, "device_points", -1.0)


class TestCoordinateNormalization:
    """Test coordinate normalization behavior."""
    
    def test_device_points_scale_1(self):
        """Coordinates already in device points use scale 1.0."""
        log = ActionLog()
        log.record_agent_click(100, 200, "device_points", 1.0)
        
        action = log._actions[0]
        assert action.normalized_x == 100.0
        assert action.normalized_y == 200.0
        assert action.raw_x == 100.0
        assert action.raw_y == 200.0
    
    def test_screen_pixels_scale_2(self):
        """Screenshot pixels at 2x retina scale correctly."""
        log = ActionLog()
        log.record_agent_click(400, 600, "screen_pixels", 2.0)
        
        action = log._actions[0]
        assert action.normalized_x == 200.0
        assert action.normalized_y == 300.0
        assert action.raw_x == 400.0
        assert action.raw_y == 600.0
    
    def test_screenshot_pixels_scale_3(self):
        """Screenshot pixels at 3x retina scale correctly."""
        log = ActionLog()
        log.record_agent_click(900, 1200, "screenshot_pixels", 3.0)
        
        action = log._actions[0]
        assert action.normalized_x == 300.0
        assert action.normalized_y == 400.0
