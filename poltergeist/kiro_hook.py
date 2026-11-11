"""The Kiro recorder hook: record the agent's simulator gestures.

Kiro runs ``poltergeist-kiro-hook`` as a command hook and writes one JSON
event to its standard input. When the tool is a simulator tap (``ui_tap``) or
swipe (``ui_swipe``), the hook records the agent's gesture on the server
through ``POST /agent-click``, in device points with scale factor 1.

Kiro does not give the model what a command hook prints, so this hook prints
nothing. The model is told to read the human's actions by an ``agent`` hook.

The hook must never fail or hang the agent: a bad input, an unreachable
server or any other error ends quietly with exit code 0 and no output.
Standard library only.
"""

import json
import math
import os
import sys
from typing import Optional
from urllib.request import Request, urlopen

DEFAULT_URL = "http://127.0.0.1:8000"
URL_ENV_VAR = "POLTERGEIST_URL"
TIMEOUT_SECONDS = 2.0

_DEVICE_POINTS = "device_points"


def _as_number(value) -> Optional[float]:
    """Return ``value`` when it is a finite number (not a bool), else ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return value


def gesture_from_event(event) -> Optional[dict]:
    """Translate a Kiro hook event into an agent-click body, or ``None``."""
    if not isinstance(event, dict):
        return None
    name = event.get("tool_name")
    tool_input = event.get("tool_input")
    if not isinstance(name, str) or not isinstance(tool_input, dict):
        return None
    name = name.lower()

    if name.endswith("ui_tap"):
        x = _as_number(tool_input.get("x"))
        y = _as_number(tool_input.get("y"))
        if x is None or y is None:
            return None
        return {
            "x": x,
            "y": y,
            "coordinate_space": _DEVICE_POINTS,
            "scale_factor": 1,
        }

    if name.endswith("ui_swipe"):
        x = _as_number(tool_input.get("x_start"))
        y = _as_number(tool_input.get("y_start"))
        end_x = _as_number(tool_input.get("x_end"))
        end_y = _as_number(tool_input.get("y_end"))
        if x is None or y is None or end_x is None or end_y is None:
            return None
        return {
            "x": x,
            "y": y,
            "end_x": end_x,
            "end_y": end_y,
            "coordinate_space": _DEVICE_POINTS,
            "scale_factor": 1,
        }

    return None


def post_agent_click(base_url: str, body: dict) -> None:
    """Send ``body`` to ``POST /agent-click`` with a short timeout."""
    request = Request(
        base_url.rstrip("/") + "/agent-click",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        response.read()


def main(stdin=None, environ=None) -> int:
    """Entry point for ``poltergeist-kiro-hook``. Always returns 0."""
    try:
        if stdin is None:
            stdin = sys.stdin
        if environ is None:
            environ = os.environ
        event = json.load(stdin)
        body = gesture_from_event(event)
        if body is not None:
            post_agent_click(environ.get(URL_ENV_VAR, DEFAULT_URL), body)
    except BaseException:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
