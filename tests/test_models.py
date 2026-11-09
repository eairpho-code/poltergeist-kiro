"""
Unit tests for core data models.

Tests dataclass instantiation, field validation, and serialization.
"""

import pytest
from dataclasses import asdict
from poltergeist.action_log import (
    UIElement,
    ClickAction,
    Mismatch,
    CoordinateScaleProblem,
    HumanActionsResponse,
)


class TestUIElement:
    """Tests for UIElement dataclass."""

    def test_instantiation_with_label(self):
        """Test creating UIElement with role and label."""
        element = UIElement(role="button", label="Submit")
        assert element.role == "button"
        assert element.label == "Submit"

    def test_instantiation_without_label(self):
        """Test creating UIElement with role only (redacted)."""
        element = UIElement(role="link")
        assert element.role == "link"
        assert element.label is None

    def test_serialization(self):
        """Test serialization to dict using asdict."""
        element = UIElement(role="text_field", label="Username")
        data = asdict(element)
        assert data == {"role": "text_field", "label": "Username"}


class TestClickAction:
    """Tests for ClickAction dataclass."""

    def test_instantiation_minimal(self):
        """Test creating ClickAction with required fields only."""
        action = ClickAction(
            timestamp="2026-05-15T14:30:45.123Z",
            actor="agent",
            normalized_x=100.0,
            normalized_y=200.0,
            raw_x=200.0,
            raw_y=400.0,
            coordinate_space="screenshot_pixels",
            scale_factor=2.0,
        )
        assert action.timestamp == "2026-05-15T14:30:45.123Z"
        assert action.actor == "agent"
        assert action.normalized_x == 100.0
        assert action.normalized_y == 200.0
        assert action.raw_x == 200.0
        assert action.raw_y == 400.0
        assert action.coordinate_space == "screenshot_pixels"
        assert action.scale_factor == 2.0
        assert action.ui_element is None

    def test_instantiation_with_ui_element(self):
        """Test creating ClickAction with UI element."""
        ui_element = UIElement(role="button", label="Login")
        action = ClickAction(
            timestamp="2026-05-15T14:30:45.123Z",
            actor="human",
            normalized_x=150.0,
            normalized_y=250.0,
            raw_x=150.0,
            raw_y=250.0,
            coordinate_space="device_points",
            scale_factor=1.0,
            ui_element=ui_element,
        )
        assert action.ui_element == ui_element
        assert action.ui_element.role == "button"
        assert action.ui_element.label == "Login"

    def test_serialization(self):
        """Test serialization to dict using asdict."""
        action = ClickAction(
            timestamp="2026-05-15T14:30:45.123Z",
            actor="agent",
            normalized_x=100.0,
            normalized_y=200.0,
            raw_x=200.0,
            raw_y=400.0,
            coordinate_space="screenshot_pixels",
            scale_factor=2.0,
            ui_element=UIElement(role="link", label="More Info"),
        )
        data = asdict(action)
        assert data["timestamp"] == "2026-05-15T14:30:45.123Z"
        assert data["actor"] == "agent"
        assert data["normalized_x"] == 100.0
        assert data["normalized_y"] == 200.0
        assert data["raw_x"] == 200.0
        assert data["raw_y"] == 400.0
        assert data["coordinate_space"] == "screenshot_pixels"
        assert data["scale_factor"] == 2.0
        assert data["ui_element"]["role"] == "link"
        assert data["ui_element"]["label"] == "More Info"


class TestMismatch:
    """Tests for Mismatch dataclass."""

    def test_instantiation(self):
        """Test creating Mismatch with agent and human clicks."""
        agent_click = ClickAction(
            timestamp="2026-05-15T14:30:45.123Z",
            actor="agent",
            normalized_x=100.0,
            normalized_y=200.0,
            raw_x=100.0,
            raw_y=200.0,
            coordinate_space="device_points",
            scale_factor=1.0,
        )
        human_click = ClickAction(
            timestamp="2026-05-15T14:30:47.456Z",
            actor="human",
            normalized_x=110.0,
            normalized_y=205.0,
            raw_x=110.0,
            raw_y=205.0,
            coordinate_space="device_points",
            scale_factor=1.0,
        )
        mismatch = Mismatch(
            agent_click=agent_click,
            human_click=human_click,
            offset_x=10.0,
            offset_y=5.0,
            distance=11.18,
        )
        assert mismatch.agent_click == agent_click
        assert mismatch.human_click == human_click
        assert mismatch.offset_x == 10.0
        assert mismatch.offset_y == 5.0
        assert mismatch.distance == 11.18

    def test_serialization(self):
        """Test serialization to dict using asdict."""
        agent_click = ClickAction(
            timestamp="2026-05-15T14:30:45.123Z",
            actor="agent",
            normalized_x=100.0,
            normalized_y=200.0,
            raw_x=100.0,
            raw_y=200.0,
            coordinate_space="device_points",
            scale_factor=1.0,
        )
        human_click = ClickAction(
            timestamp="2026-05-15T14:30:47.456Z",
            actor="human",
            normalized_x=110.0,
            normalized_y=205.0,
            raw_x=110.0,
            raw_y=205.0,
            coordinate_space="device_points",
            scale_factor=1.0,
        )
        mismatch = Mismatch(
            agent_click=agent_click,
            human_click=human_click,
            offset_x=10.0,
            offset_y=5.0,
            distance=11.18,
        )
        data = asdict(mismatch)
        assert data["offset_x"] == 10.0
        assert data["offset_y"] == 5.0
        assert data["distance"] == 11.18
        assert data["agent_click"]["actor"] == "agent"
        assert data["human_click"]["actor"] == "human"


class TestCoordinateScaleProblem:
    """Tests for CoordinateScaleProblem dataclass."""

    def test_instantiation(self):
        """Test creating CoordinateScaleProblem."""
        problem = CoordinateScaleProblem(
            sample_size=5,
            scale_x=2.01,
            scale_y=1.99,
            spread_x=0.05,
            spread_y=0.06,
        )
        assert problem.sample_size == 5
        assert problem.scale_x == 2.01
        assert problem.scale_y == 1.99
        assert problem.spread_x == 0.05
        assert problem.spread_y == 0.06

    def test_serialization(self):
        """Test serialization to dict using asdict."""
        problem = CoordinateScaleProblem(
            sample_size=3,
            scale_x=1.5,
            scale_y=1.5,
            spread_x=0.02,
            spread_y=0.03,
        )
        data = asdict(problem)
        assert data == {
            "sample_size": 3,
            "scale_x": 1.5,
            "scale_y": 1.5,
            "spread_x": 0.02,
            "spread_y": 0.03,
        }


class TestHumanActionsResponse:
    """Tests for HumanActionsResponse dataclass."""

    def test_instantiation_minimal(self):
        """Test creating HumanActionsResponse without scale problem."""
        response = HumanActionsResponse(
            human_actions=[],
            mismatches=[],
        )
        assert response.human_actions == []
        assert response.mismatches == []
        assert response.coordinate_scale_problem is None

    def test_instantiation_with_scale_problem(self):
        """Test creating HumanActionsResponse with scale problem."""
        problem = CoordinateScaleProblem(
            sample_size=3,
            scale_x=2.0,
            scale_y=2.0,
            spread_x=0.05,
            spread_y=0.05,
        )
        response = HumanActionsResponse(
            human_actions=[],
            mismatches=[],
            coordinate_scale_problem=problem,
        )
        assert response.coordinate_scale_problem == problem

    def test_serialization(self):
        """Test serialization to dict using asdict."""
        human_action = ClickAction(
            timestamp="2026-05-15T14:30:47.456Z",
            actor="human",
            normalized_x=110.0,
            normalized_y=205.0,
            raw_x=110.0,
            raw_y=205.0,
            coordinate_space="device_points",
            scale_factor=1.0,
        )
        response = HumanActionsResponse(
            human_actions=[human_action],
            mismatches=[],
            coordinate_scale_problem=None,
        )
        data = asdict(response)
        assert len(data["human_actions"]) == 1
        assert data["human_actions"][0]["actor"] == "human"
        assert data["mismatches"] == []
        assert data["coordinate_scale_problem"] is None
