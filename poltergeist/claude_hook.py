"""The Claude Code hook: tell the agent what the human did after each action.

Claude Code runs ``poltergeist-claude-hook`` after each tool call. When the
tool is the iOS simulator, the hook records the agent's gesture on the server
and reports the human's actions since the agent's previous simulator action,
so the agent knows the screen may have changed under it.

The hook must never fail or hang the agent: an unreachable server, bad input,
or any other error ends quietly with exit code 0 and no output.
"""

import json
import os
import re
import sys
import tempfile
from typing import List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from poltergeist.activity import describe_activity, scale_changed

DEFAULT_URL = "http://127.0.0.1:8000"
URL_ENV_VAR = "POLTERGEIST_URL"
STATE_DIR_ENV_VAR = "POLTERGEIST_HOOK_STATE_DIR"

_DEVICE_POINTS = "device_points"

_HEADER = (
    "Poltergeist: since your last simulator action, the human also acted in "
    "the Simulator, so the screen may not be where you left it:"
)


def is_simulator_tool(name: Optional[str]) -> bool:
    """True when ``name`` is the iOS simulator tool.

    A tool qualifies when its lower-cased name starts with ``mcp__`` and
    contains ``ios_simulator``.
    """
    if not isinstance(name, str):
        return False
    lowered = name.lower()
    return lowered.startswith("mcp__") and "ios_simulator" in lowered


def _as_number(value) -> Optional[float]:
    """Return ``value`` as a float when it is a real number, else ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _click_body(x: float, y: float) -> dict:
    return {
        "x": x,
        "y": y,
        "coordinate_space": _DEVICE_POINTS,
        "scale_factor": 1.0,
    }


def _drag_body(x: float, y: float, end_x: float, end_y: float) -> dict:
    body = _click_body(x, y)
    body["end_x"] = end_x
    body["end_y"] = end_y
    return body


def agent_gesture(tool_input) -> Optional[dict]:
    """Translate a simulator tool input into an agent-click body.

    - ``tap`` becomes a click from ``x``/``y``.
    - ``swipe`` becomes a drag from ``x``/``y`` to ``x2``/``y2``.
    - ``touch_path`` becomes a drag from the first to the last point, or a
      click when they are equal or there is a single point.

    Everything is in device points with scale factor 1. Anything else, or
    malformed input, returns ``None``.
    """
    if not isinstance(tool_input, dict):
        return None

    action = tool_input.get("action")

    if action == "tap":
        x = _as_number(tool_input.get("x"))
        y = _as_number(tool_input.get("y"))
        if x is None or y is None:
            return None
        return _click_body(x, y)

    if action == "swipe":
        x = _as_number(tool_input.get("x"))
        y = _as_number(tool_input.get("y"))
        end_x = _as_number(tool_input.get("x2"))
        end_y = _as_number(tool_input.get("y2"))
        if None in (x, y, end_x, end_y):
            return None
        return _drag_body(x, y, end_x, end_y)

    if action == "touch_path":
        points = tool_input.get("points")
        if not isinstance(points, list) or not points:
            return None
        first = points[0]
        last = points[-1]
        if not isinstance(first, dict) or not isinstance(last, dict):
            return None
        x = _as_number(first.get("x"))
        y = _as_number(first.get("y"))
        end_x = _as_number(last.get("x"))
        end_y = _as_number(last.get("y"))
        if x is None or y is None or end_x is None or end_y is None:
            return None
        if (x, y) == (end_x, end_y):
            return _click_body(x, y)
        return _drag_body(x, y, end_x, end_y)

    return None


class Server:
    """Talk to the poltergeist server over HTTP for the hook."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def record_agent(self, body: dict) -> None:
        """Record the agent's gesture through ``POST /agent-click``."""
        data = json.dumps(body).encode("utf-8")
        request = Request(
            self._base_url + "/agent-click",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2.0) as response:
            response.read()

    def human_actions(self, since: Optional[str]) -> dict:
        """Fetch ``GET /human-actions`` with a two second timeout."""
        url = self._base_url + "/human-actions"
        if since:
            url = url + "?" + urlencode({"since": since})
        with urlopen(url, timeout=2.0) as response:
            return json.loads(response.read().decode("utf-8"))


class CursorStore:
    """Persist one session's cursor in a JSON file in the state directory."""

    def __init__(self, session_id: str, directory: Optional[str] = None) -> None:
        self._session_id = self._safe_id(session_id)
        self._directory = directory if directory is not None else tempfile.gettempdir()
        self._path = os.path.join(
            self._directory, f"poltergeist-hook-{self._session_id}.json"
        )

    @staticmethod
    def _safe_id(session_id) -> str:
        """Reduce a session id to letters, digits, ``-`` and ``_``."""
        text = str(session_id) if session_id is not None else "default"
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", text)
        return cleaned or "default"

    def _read(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict) -> None:
        try:
            os.makedirs(self._directory, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
        except OSError:
            pass

    def load(self) -> Optional[str]:
        """Return the stored cursor, or ``None`` when there is none."""
        cursor = self._read().get("cursor")
        return cursor if isinstance(cursor, str) else None

    def save(self, cursor: str) -> None:
        """Store ``cursor`` for this session, keeping a stored scale."""
        data = self._read()
        data["cursor"] = cursor
        self._write(data)

    def load_scale(self) -> Optional[dict]:
        """Return the reported scale (``scale_x``, ``scale_y``) or ``None``."""
        scale = self._read().get("scale")
        if not isinstance(scale, dict):
            return None
        x, y = scale.get("scale_x"), scale.get("scale_y")
        if _as_number(x) is None or _as_number(y) is None:
            return None
        return {"scale_x": x, "scale_y": y}

    def save_scale(self, problem: Optional[dict]) -> None:
        """Store the scale of ``problem``, or remove the stored scale for ``None``."""
        data = self._read()
        if problem is None:
            if "scale" not in data:
                return
            del data["scale"]
        else:
            data["scale"] = {
                "scale_x": problem["scale_x"],
                "scale_y": problem["scale_y"],
            }
        self._write(data)


def context_for(lines: List[str]) -> str:
    """Build the additional-context text from description lines."""
    body = "\n".join(f"- {line}" for line in lines)
    return f"{_HEADER}\n{body}"


def handle_event(event, server: Server, cursor: CursorStore) -> Optional[str]:
    """Handle one Claude Code PostToolUse event.

    Ignores non-simulator tools. Records the agent's gesture if any (errors
    swallowed). On the first call of a session it only remembers the server
    time and returns ``None``; afterwards it returns the context text for the
    human's new actions, or ``None`` when there is nothing new.
    """
    if not isinstance(event, dict):
        return None

    if not is_simulator_tool(event.get("tool_name")):
        return None

    gesture = agent_gesture(event.get("tool_input"))
    if gesture is not None:
        try:
            server.record_agent(gesture)
        except Exception:
            pass

    previous = cursor.load()

    payload = server.human_actions(previous)

    if previous is None:
        # First call of this session: remember the server time, say nothing.
        server_time = payload.get("server_time")
        if server_time:
            cursor.save(server_time)
        cursor.save_scale(payload.get("coordinate_scale_problem"))
        return None

    actions = payload.get("human_actions", [])
    if actions:
        cursor.save(actions[-1]["timestamp"])

    problem = payload.get("coordinate_scale_problem")
    if scale_changed(cursor.load_scale(), problem):
        cursor.save_scale(problem)
    else:
        payload = dict(payload, coordinate_scale_problem=None)
        if problem is None:
            cursor.save_scale(None)

    lines = describe_activity(payload)
    if not lines:
        return None

    return context_for(lines)


def main(stdin=None, stdout=None, environ=None) -> int:
    """Entry point for ``poltergeist-claude-hook``. Always returns 0."""
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    if environ is None:
        environ = os.environ

    try:
        event = json.load(stdin)
    except Exception:
        return 0

    try:
        base_url = environ.get(URL_ENV_VAR, DEFAULT_URL)
        state_dir = environ.get(STATE_DIR_ENV_VAR)
        session_id = event.get("session_id") if isinstance(event, dict) else None

        server = Server(base_url)
        cursor = CursorStore(session_id, state_dir)

        context = handle_event(event, server, cursor)
    except Exception:
        return 0

    if context:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
        try:
            stdout.write(json.dumps(output))
        except Exception:
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
