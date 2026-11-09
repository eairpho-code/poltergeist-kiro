"""Core data models and the in-memory Action Log store.

This module defines the dataclasses that make up the action log
(UIElement, ClickAction, Mismatch, CoordinateScaleProblem, HumanActionsResponse)
and the ActionLog class, which records agent and human click actions in memory.

Only the recording side (record_agent_click / record_human_click) is implemented
here. Mismatch detection, scale-problem detection, query methods, and the MCP
server belong to later stages.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from poltergeist.normalize import normalize_coordinates, validate_coordinate_space

# Maximum length of a UI element short label.
MAX_LABEL_LENGTH = 50

# Environment variable that enables UI element label redaction.
REDACT_ENV_VAR = "POLTERGEIST_REDACT_UI_LABELS"

# String values (case-insensitive) that enable redaction.
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass
class UIElement:
    """Identifier for the target of a click.

    Stores only the role (e.g. "button", "link") and a short label. Long
    on-screen text is never stored here. When redaction is enabled the label
    is omitted (None).
    """

    role: str
    label: Optional[str] = None


@dataclass
class ClickAction:
    """A recorded click event from a human or an agent."""

    timestamp: str  # UTC ISO 8601 with milliseconds: "2026-05-15T14:30:45.123Z"
    actor: str  # "agent" or "human"
    normalized_x: float  # Device points
    normalized_y: float  # Device points
    raw_x: float  # Original coordinates
    raw_y: float  # Original coordinates
    coordinate_space: str  # "device_points", "screen_pixels", "screenshot_pixels"
    scale_factor: float  # Conversion ratio used for normalization
    ui_element: Optional[UIElement] = None


@dataclass
class Mismatch:
    """An agent click that was followed shortly after by a human click."""

    agent_click: ClickAction
    human_click: ClickAction
    offset_x: float  # human_x - agent_x (device points)
    offset_y: float  # human_y - agent_y (device points)
    distance: float  # Euclidean distance (device points)


@dataclass
class CoordinateScaleProblem:
    """A systematic coordinate scaling issue across multiple mismatches."""

    sample_size: int  # Number of mismatches with valid scale samples
    scale_x: float  # Mean of agent_x / human_x ratios
    scale_y: float  # Mean of agent_y / human_y ratios
    spread_x: float  # Relative spread (std_dev / mean) in x dimension
    spread_y: float  # Relative spread (std_dev / mean) in y dimension


@dataclass
class HumanActionsResponse:
    """The result of querying human actions, with detection results."""

    human_actions: List[ClickAction]
    mismatches: List[Mismatch]
    coordinate_scale_problem: Optional[CoordinateScaleProblem] = None


def _default_clock() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


def _format_timestamp(moment: datetime) -> str:
    """Format a datetime as UTC ISO 8601 with millisecond precision and a 'Z'.

    Example: "2026-05-15T14:30:45.123Z".
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _redaction_enabled() -> bool:
    """Return True when the redaction environment switch is enabled."""
    value = os.environ.get(REDACT_ENV_VAR)
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


class ActionLog:
    """In-memory store of click actions from humans and agents."""

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._actions: List[ClickAction] = []
        self._clock = clock if clock is not None else _default_clock

    def _now_timestamp(self) -> str:
        return _format_timestamp(self._clock())

    def _prepare_ui_element(
        self, ui_element: Optional[UIElement]
    ) -> Optional[UIElement]:
        """Apply redaction and label truncation to a UI element.

        Returns a new UIElement (leaving the caller's object untouched):
        - When redaction is enabled, the label is dropped (None).
        - Otherwise the label is truncated to MAX_LABEL_LENGTH characters.
        """
        if ui_element is None:
            return None

        if _redaction_enabled():
            return UIElement(role=ui_element.role, label=None)

        label = ui_element.label
        if label is not None and len(label) > MAX_LABEL_LENGTH:
            label = label[:MAX_LABEL_LENGTH]
        return UIElement(role=ui_element.role, label=label)

    def _record(
        self,
        actor: str,
        x: float,
        y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement],
    ) -> None:
        validate_coordinate_space(coordinate_space)
        normalized_x, normalized_y = normalize_coordinates(x, y, scale_factor)
        action = ClickAction(
            timestamp=self._now_timestamp(),
            actor=actor,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            raw_x=x,
            raw_y=y,
            coordinate_space=coordinate_space,
            scale_factor=scale_factor,
            ui_element=self._prepare_ui_element(ui_element),
        )
        self._actions.append(action)

    def record_agent_click(
        self,
        x: float,
        y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> None:
        """Record an agent click action with coordinate normalization."""
        self._record("agent", x, y, coordinate_space, scale_factor, ui_element)

    def record_human_click(
        self,
        x: float,
        y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> None:
        """Record a human click action with coordinate normalization."""
        self._record("human", x, y, coordinate_space, scale_factor, ui_element)
