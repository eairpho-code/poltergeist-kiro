"""Core data models and the in-memory Action Log store.

This module defines the dataclasses that make up the action log
(UIElement, ClickAction, Mismatch, CoordinateScaleProblem, HumanActionsResponse)
and the ActionLog class, which records agent and human click actions in memory.

Only the recording side (record_agent_click / record_human_click) is implemented
here. Mismatch detection, scale-problem detection, query methods, and the MCP
server belong to later stages.
"""

import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from poltergeist.normalize import normalize_coordinates, validate_coordinate_space

logger = logging.getLogger("poltergeist.action_log")

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
    kind: str = "click"  # "click" (a single press) or "drag" (press-move-release)
    end_x: Optional[float] = None  # Normalized end point (device points); None for a click
    end_y: Optional[float] = None  # Normalized end point (device points); None for a click


@dataclass
class Mismatch:
    """An agent click that was followed shortly after by a human click."""

    agent_click: ClickAction
    human_click: ClickAction
    offset_x: float  # human_x - agent_x (device points)
    offset_y: float  # human_y - agent_y (device points)
    distance: float  # Euclidean distance (device points)
    # agent / human for this pair alone (device points); None when the human
    # coordinate is below the near-zero threshold in absolute value.
    ratio_x: Optional[float] = None
    ratio_y: Optional[float] = None


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


def _parse_iso_timestamp(timestamp: str) -> datetime:
    """Parse a UTC ISO 8601 timestamp (trailing 'Z' allowed) to a datetime.

    Raises:
        ValueError: If the string is not a valid ISO 8601 timestamp. The
            message matches the format documented for the MCP tools.
    """
    try:
        normalized = timestamp.replace("Z", "+00:00")
        moment = datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        raise ValueError(
            "timestamp must be UTC ISO 8601 with milliseconds "
            "(e.g., 2026-05-15T14:30:45.123Z)"
        )
    if moment.tzinfo is None:
        # A bare date or datetime with no zone is ambiguous; the contract is a
        # UTC ISO 8601 timestamp, which must carry a time-zone marker.
        raise ValueError(
            "timestamp must be UTC ISO 8601 with milliseconds "
            "(e.g., 2026-05-15T14:30:45.123Z)"
        )
    return moment


def parse_timestamp(timestamp: str) -> datetime:
    """Public name for the UTC ISO 8601 timestamp parser.

    Raises:
        ValueError: If the string is not a valid UTC ISO 8601 timestamp.
    """
    return _parse_iso_timestamp(timestamp)


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

    def now(self) -> str:
        """Return the current time of the log's clock as a UTC ISO 8601 timestamp.

        The format matches recorded timestamps: milliseconds and a trailing
        ``Z`` (e.g. ``"2026-05-15T14:30:00.000Z"``). The server uses this for
        ``server_time``.
        """
        return self._now_timestamp()

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
            logger.warning(
                "UI element label truncated from %d to %d characters",
                len(label),
                MAX_LABEL_LENGTH,
            )
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
        end: Optional[tuple] = None,
    ) -> ClickAction:
        validate_coordinate_space(coordinate_space)
        normalized_x, normalized_y = normalize_coordinates(x, y, scale_factor)

        kind = "click"
        end_x: Optional[float] = None
        end_y: Optional[float] = None
        if end is not None:
            raw_end_x, raw_end_y = end
            if not math.isfinite(raw_end_x) or not math.isfinite(raw_end_y):
                raise ValueError("end_x and end_y must be finite")
            # The end point is divided by the same scale factor as the start.
            end_x, end_y = normalize_coordinates(raw_end_x, raw_end_y, scale_factor)
            kind = "drag"

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
            kind=kind,
            end_x=end_x,
            end_y=end_y,
        )
        self._actions.append(action)
        return action

    def record_agent_click(
        self,
        x: float,
        y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> ClickAction:
        """Record an agent click action with coordinate normalization.

        Returns the recorded :class:`ClickAction`.
        """
        return self._record("agent", x, y, coordinate_space, scale_factor, ui_element)

    def record_human_click(
        self,
        x: float,
        y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> ClickAction:
        """Record a human click action with coordinate normalization.

        Returns the recorded :class:`ClickAction`.
        """
        return self._record("human", x, y, coordinate_space, scale_factor, ui_element)

    def record_agent_drag(
        self,
        x: float,
        y: float,
        end_x: float,
        end_y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> ClickAction:
        """Record an agent drag (press at start, release at end).

        The end point is normalized with the same ``scale_factor`` as the
        start. Returns the recorded :class:`ClickAction` with kind ``"drag"``.
        """
        return self._record(
            "agent", x, y, coordinate_space, scale_factor, ui_element, end=(end_x, end_y)
        )

    def record_human_drag(
        self,
        x: float,
        y: float,
        end_x: float,
        end_y: float,
        coordinate_space: str,
        scale_factor: float,
        ui_element: Optional[UIElement] = None,
    ) -> ClickAction:
        """Record a human drag (press at start, release at end).

        The end point is normalized with the same ``scale_factor`` as the
        start. Returns the recorded :class:`ClickAction` with kind ``"drag"``.
        """
        return self._record(
            "human", x, y, coordinate_space, scale_factor, ui_element, end=(end_x, end_y)
        )

    def get_human_actions(
        self,
        since_timestamp: Optional[str] = None,
    ) -> HumanActionsResponse:
        """Retrieve human actions after the given timestamp (exclusive).

        Human clicks are returned in chronological order (oldest first). When
        ``since_timestamp`` is omitted, all human actions are returned.
        Mismatch and coordinate-scale-problem detection run over the full
        action log so that agent clicks preceding a human click are considered.

        Args:
            since_timestamp: Optional UTC ISO 8601 timestamp (exclusive). Only
                human clicks recorded strictly after this moment are returned.

        Raises:
            ValueError: If ``since_timestamp`` is not a valid UTC ISO 8601
                timestamp.

        Returns:
            A ``HumanActionsResponse`` with the filtered human actions, the
            detected mismatches, and an optional coordinate scale problem.
        """
        since_moment = (
            _parse_iso_timestamp(since_timestamp)
            if since_timestamp is not None
            else None
        )

        # Sort the full log chronologically so detection sees correct ordering.
        sorted_actions = sorted(
            self._actions, key=lambda click: _parse_iso_timestamp(click.timestamp)
        )

        human_actions: List[ClickAction] = []
        for action in sorted_actions:
            if action.actor != "human":
                continue
            if since_moment is not None:
                action_moment = _parse_iso_timestamp(action.timestamp)
                if action_moment <= since_moment:
                    continue
            human_actions.append(action)

        from poltergeist.detection import detect_mismatches, detect_scale_problem

        all_mismatches = detect_mismatches(sorted_actions)

        if since_moment is None:
            mismatches = all_mismatches
        else:
            # Only report mismatches whose human correction falls in the
            # window the caller asked about. Detection still runs over the full
            # log so that agent clicks preceding the window are considered.
            returned_humans = set(id(action) for action in human_actions)
            mismatches = [
                m for m in all_mismatches if id(m.human_click) in returned_humans
            ]

        # The scale problem belongs to the whole log, whatever the cursor.
        scale_problem = detect_scale_problem(all_mismatches)

        return HumanActionsResponse(
            human_actions=human_actions,
            mismatches=mismatches,
            coordinate_scale_problem=scale_problem,
        )

    def clear(self, before_timestamp: Optional[str] = None) -> int:
        """Remove actions before the given timestamp (exclusive).

        When ``before_timestamp`` is omitted, every action is removed.

        Args:
            before_timestamp: Optional UTC ISO 8601 timestamp (exclusive).
                Actions recorded strictly before this moment are removed.

        Raises:
            ValueError: If ``before_timestamp`` is not a valid UTC ISO 8601
                timestamp.

        Returns:
            The number of actions removed.
        """
        if before_timestamp is None:
            removed = len(self._actions)
            self._actions = []
            return removed

        before_moment = _parse_iso_timestamp(before_timestamp)

        kept: List[ClickAction] = []
        removed = 0
        for action in self._actions:
            if _parse_iso_timestamp(action.timestamp) < before_moment:
                removed += 1
            else:
                kept.append(action)
        self._actions = kept
        return removed
