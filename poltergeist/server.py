"""MCP server for the human action log.

This module wires the in-memory :class:`~poltergeist.action_log.ActionLog`
to the outside world through two channels:

- Three MCP tools that AI agents call over stdio or Streamable HTTP:
  ``record_agent_click``, ``get_human_actions`` and ``clear_action_log``.
- A plain HTTP ``POST /human-click`` endpoint that external human-observer
  components use to record human clicks.

The file is meant to be run directly as a script (``python server.py``); the
package is not necessarily installed, so it fixes up ``sys.path`` before
importing the ``poltergeist`` package. Agent clicks arrive via the MCP tool and
are tagged ``actor="agent"``; human clicks arrive via the HTTP endpoint and are
tagged ``actor="human"``.

Transport selection is controlled by environment variables so the test suite
can launch the server as a subprocess:

- ``POLTERGEIST_TRANSPORT``: "stdio" (default) or "streamable-http".
- ``POLTERGEIST_HOST``: bind address for HTTP (default "127.0.0.1").
- ``POLTERGEIST_PORT``: bind port for HTTP (default 8000).

Logging is configured through :mod:`poltergeist.logging_config`, which sends
records to stderr at the level named by ``POLTERGEIST_LOG_LEVEL``.
"""

import json
import logging
import os
import sys
import math
from pathlib import Path
from typing import Optional

# When run as a script (``python poltergeist/server.py``) the package root is
# not on sys.path. Add the parent directory so ``import poltergeist`` works even
# though the package is not installed.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

from poltergeist.action_log import ActionLog, UIElement
from poltergeist.logging_config import configure_logging
from poltergeist.normalize import validate_coordinate_space

logger = logging.getLogger("poltergeist.server")


# --- Server and shared state ---------------------------------------------------

mcp = MCPServer("poltergeist-human-action-log")

# A single in-memory action log shared by every tool call and HTTP request in
# this process. It disappears when the process exits (in-memory only).
action_log = ActionLog()


# --- Validation helpers --------------------------------------------------------


def _validate_scale_factor(scale_factor: float) -> None:
    """Raise ValueError when scale_factor is not a finite number > 0."""
    if not math.isfinite(scale_factor) or scale_factor <= 0:
        raise ValueError("scale_factor must be greater than 0")


def _validate_coordinates(x: float, y: float) -> None:
    """Raise ValueError when either coordinate is not a finite number."""
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("x and y must be finite")


def _record_and_timestamp(record, *args) -> str:
    """Call a record_* method then return the timestamp of the new action."""
    record(*args)
    # The action just appended is the most recent one in the log.
    return action_log._actions[-1].timestamp


class _anticipated:
    """Translate anticipated ValueErrors into ToolError.

    A plain exception raised in a tool body is wrapped by the SDK as an
    ``UnexpectedToolError`` whose message is generic ("Error executing tool
    ..."). Validation failures are anticipated, so we re-raise them as
    ``ToolError``, which preserves the message verbatim in the error result the
    agent receives.
    """

    def __enter__(self) -> "_anticipated":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if isinstance(exc, ValueError):
            logger.warning("rejected: %s", exc)
            raise ToolError(str(exc)) from exc
        return False


# --- MCP tools -----------------------------------------------------------------


@mcp.tool()
def record_agent_click(
    x: float,
    y: float,
    coordinate_space: str,
    scale_factor: float,
    ui_element_role: Optional[str] = None,
    ui_element_label: Optional[str] = None,
) -> dict:
    """Record an agent click action.

    Args:
        x: Raw x coordinate.
        y: Raw y coordinate.
        coordinate_space: One of "device_points", "screen_pixels",
            "screenshot_pixels".
        scale_factor: Conversion ratio to device points (e.g. 2.0 for 2x
            retina). Must be greater than 0.
        ui_element_role: Optional UI element role (e.g. "button", "link").
        ui_element_label: Optional short label (truncated to 50 characters).

    Returns:
        A dict with ``status``, ``actor`` and the recorded ``timestamp``.
    """
    logger.info("record_agent_click x=%r y=%r space=%r scale=%r", x, y, coordinate_space, scale_factor)
    with _anticipated():
        validate_coordinate_space(coordinate_space)
        _validate_coordinates(x, y)
        _validate_scale_factor(scale_factor)

        ui_element = None
        if ui_element_role:
            ui_element = UIElement(role=ui_element_role, label=ui_element_label)

        timestamp = _record_and_timestamp(
            action_log.record_agent_click, x, y, coordinate_space, scale_factor, ui_element
        )
    return {"status": "recorded", "actor": "agent", "timestamp": timestamp}


@mcp.tool()
def get_human_actions(since_timestamp: Optional[str] = None) -> dict:
    """Retrieve human click actions with mismatch detection.

    Args:
        since_timestamp: Optional UTC ISO 8601 timestamp (exclusive). When
            omitted, all human actions are returned.

    Returns:
        A dict with ``human_actions``, ``mismatches`` and
        ``coordinate_scale_problem`` (``None`` when no scale problem).
    """
    logger.info("get_human_actions since=%r", since_timestamp)
    with _anticipated():
        response = action_log.get_human_actions(since_timestamp)
    return {
        "human_actions": [_click_to_dict(a) for a in response.human_actions],
        "mismatches": [_mismatch_to_dict(m) for m in response.mismatches],
        "coordinate_scale_problem": (
            _scale_problem_to_dict(response.coordinate_scale_problem)
            if response.coordinate_scale_problem is not None
            else None
        ),
    }


@mcp.tool()
def clear_action_log(before_timestamp: Optional[str] = None) -> dict:
    """Clear action log entries.

    Args:
        before_timestamp: Optional UTC ISO 8601 timestamp (exclusive). When
            omitted, all actions are removed.

    Returns:
        A dict with ``removed_count``.
    """
    logger.info("clear_action_log before=%r", before_timestamp)
    with _anticipated():
        count = action_log.clear(before_timestamp)
    return {"removed_count": count}


# --- Serialization helpers -----------------------------------------------------


def _ui_element_to_dict(ui_element: Optional[UIElement]) -> Optional[dict]:
    if ui_element is None:
        return None
    return {"role": ui_element.role, "label": ui_element.label}


def _click_to_dict(click) -> dict:
    return {
        "timestamp": click.timestamp,
        "actor": click.actor,
        "normalized_x": click.normalized_x,
        "normalized_y": click.normalized_y,
        "raw_x": click.raw_x,
        "raw_y": click.raw_y,
        "coordinate_space": click.coordinate_space,
        "scale_factor": click.scale_factor,
        "ui_element": _ui_element_to_dict(click.ui_element),
    }


def _mismatch_to_dict(mismatch) -> dict:
    return {
        "agent_click": _click_to_dict(mismatch.agent_click),
        "human_click": _click_to_dict(mismatch.human_click),
        "offset_x": mismatch.offset_x,
        "offset_y": mismatch.offset_y,
        "distance": mismatch.distance,
    }


def _scale_problem_to_dict(problem) -> dict:
    return {
        "sample_size": problem.sample_size,
        "scale_x": problem.scale_x,
        "scale_y": problem.scale_y,
        "spread_x": problem.spread_x,
        "spread_y": problem.spread_y,
    }


# --- HTTP endpoint for human clicks --------------------------------------------

_REQUIRED_HUMAN_CLICK_FIELDS = ("x", "y", "coordinate_space", "scale_factor")


@mcp.custom_route("/human-click", methods=["POST"])
async def handle_human_click(request: Request) -> JSONResponse:
    """Record a human click from an external observer component.

    Expects a JSON body with ``x``, ``y``, ``coordinate_space`` and
    ``scale_factor`` and an optional ``ui_element`` object (``role`` and
    ``label``). Returns 200 with the recorded timestamp on success, or 400
    with an ``error`` message on bad input.
    """
    try:
        data = await request.json()
    except Exception:
        logger.warning("human-click: invalid JSON body")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if not isinstance(data, dict):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    missing = [f for f in _REQUIRED_HUMAN_CLICK_FIELDS if f not in data]
    if missing:
        logger.warning("human-click: missing fields %r", missing)
        return JSONResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"},
            status_code=400,
        )

    x = data["x"]
    y = data["y"]
    coordinate_space = data["coordinate_space"]
    scale_factor = data["scale_factor"]

    try:
        validate_coordinate_space(coordinate_space)
        _validate_scale_factor(scale_factor)
    except ValueError as exc:
        logger.warning("human-click: validation failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=400)

    ui_element = None
    raw_ui = data.get("ui_element")
    if isinstance(raw_ui, dict) and raw_ui.get("role"):
        ui_element = UIElement(role=raw_ui["role"], label=raw_ui.get("label"))

    try:
        timestamp = _record_and_timestamp(
            action_log.record_human_click,
            x,
            y,
            coordinate_space,
            scale_factor,
            ui_element,
        )
    except ValueError as exc:
        logger.warning("human-click: validation failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        logger.error("/human-click failed while recording the click", exc_info=True)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    logger.info("/human-click recorded at %s", timestamp)
    return JSONResponse(
        {"status": "recorded", "actor": "human", "timestamp": timestamp},
        status_code=200,
    )


# --- Entry point ---------------------------------------------------------------


def main() -> None:
    """Run the server using the transport chosen by the environment."""
    configure_logging()

    transport = os.environ.get("POLTERGEIST_TRANSPORT", "stdio")

    if transport == "streamable-http":
        host = os.environ.get("POLTERGEIST_HOST", "127.0.0.1")
        port = int(os.environ.get("POLTERGEIST_PORT", "8000"))
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
