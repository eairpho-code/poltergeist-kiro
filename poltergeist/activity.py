"""Turn the dictionaries of the read route into short English sentences.

These are pure functions that work on the plain dictionaries returned by
``GET /human-actions`` (the same shape as the ``get_human_actions`` tool),
never on the dataclasses. The watcher and the Claude Code hook use them to
tell an agent what a human did, without the agent parsing JSON.
"""

from typing import List, Optional

from poltergeist.action_log import parse_timestamp


def _format_coord(value: float) -> str:
    """Format a single coordinate with one decimal place."""
    return f"{value:.1f}"


def _format_point(x: float, y: float) -> str:
    """Format a point as ``(x, y)`` with one decimal each."""
    return f"({_format_coord(x)}, {_format_coord(y)})"


def _format_time(timestamp: str) -> str:
    """Return the ``HH:MM:SS UTC`` time of a UTC ISO 8601 timestamp."""
    moment = parse_timestamp(timestamp)
    return moment.strftime("%H:%M:%S") + " UTC"


def _role_of(action: dict) -> Optional[str]:
    """Return the UI element role of an action, or ``None`` when unknown."""
    ui_element = action.get("ui_element")
    if isinstance(ui_element, dict):
        role = ui_element.get("role")
        if role:
            return role
    return None


def describe_action(action: dict) -> str:
    """Describe a single human action as one sentence.

    A click becomes ``the human clicked (x, y) at HH:MM:SS UTC`` and a drag
    becomes ``the human dragged from (x, y) to (x, y) at HH:MM:SS UTC``. When
    the UI element role is known, `` on a <role>`` is inserted before `` at``.
    Coordinates carry one decimal.
    """
    start = _format_point(action["normalized_x"], action["normalized_y"])

    if action.get("kind") == "drag":
        end = _format_point(action["end_x"], action["end_y"])
        body = f"the human dragged from {start} to {end}"
    else:
        body = f"the human clicked {start}"

    role = _role_of(action)
    if role is not None:
        body += f" on a {role}"

    return f"{body} at {_format_time(action['timestamp'])}"


def _signed(value: float) -> str:
    """Format a signed offset with one decimal (always a leading + or -)."""
    return f"{value:+.1f}"


def describe_mismatch(mismatch: dict) -> str:
    """Describe a mismatch: how long after and how far off the human clicked.

    Ends with the sentence from Requirement 6.4 so the agent understands the
    click probably missed.
    """
    agent = mismatch["agent_click"]
    human = mismatch["human_click"]

    seconds = (
        parse_timestamp(human["timestamp"]) - parse_timestamp(agent["timestamp"])
    ).total_seconds()

    human_point = _format_point(human["normalized_x"], human["normalized_y"])
    agent_point = _format_point(agent["normalized_x"], agent["normalized_y"])
    offset = f"({_signed(mismatch['offset_x'])}, {_signed(mismatch['offset_y'])})"

    return (
        f"the human's click at {human_point} came {seconds:.1f}s after the "
        f"agent's click at {agent_point}, offset {offset}: that click probably "
        f"missed or did something the human did not want"
    )


def describe_scale_problem(problem: dict) -> str:
    """Describe a coordinate scale problem in words (Requirement 6.5)."""
    return (
        f"the agent's clicks miss by a consistent factor of about "
        f"x{problem['scale_x']:.2f} horizontally and x{problem['scale_y']:.2f} "
        f"vertically ({problem['sample_size']} samples): its coordinates are "
        f"probably on the wrong scale"
    )


def describe_activity(payload: dict) -> List[str]:
    """Describe a whole read-route payload as a list of lines.

    The human actions come first (oldest first, as the route returns them),
    then the mismatches, then the coordinate scale problem. An empty payload
    yields an empty list.
    """
    lines: List[str] = []

    for action in payload.get("human_actions", []):
        lines.append(describe_action(action))

    for mismatch in payload.get("mismatches", []):
        lines.append(describe_mismatch(mismatch))

    problem = payload.get("coordinate_scale_problem")
    if problem is not None:
        lines.append(describe_scale_problem(problem))

    return lines
