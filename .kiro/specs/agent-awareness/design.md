# Design Document

## Overview

This design extends the existing package. It changes `action_log.py`, `detection.py` and `server.py`, and adds three modules: `activity.py`, `watch.py` and `claude_hook.py`. Everything stays in memory and every time is UTC.

```
 human / observer ──POST /human-click──▶ ┐
 observer / hook  ──POST /agent-click──▶ ├─ server.py ── ActionLog ── detection.py
 watcher / hook   ──GET  /human-actions─▶ ┘                 │
                                                    activity.py (words)
 watch.py ─┐
 claude_hook.py ─┴─ read the route, print sentences
```

## Changes to existing modules

### action_log.py

- `ClickAction` gains `kind: str = "click"`, `end_x: Optional[float] = None`, `end_y: Optional[float] = None`. For a drag the start is `normalized_x`/`normalized_y` and the end is `end_x`/`end_y`, both in device points.
- `ActionLog._record_click` takes an optional `end` pair. The end point is divided by the same `scale_factor` as the start. A non-finite end raises `ValueError("end_x and end_y must be finite")` before anything is stored.
- New public methods: `record_human_drag` and `record_agent_drag`, with the arguments `x, y, end_x, end_y, coordinate_space, scale_factor, ui_element=None`.
- `now()` returns the current time of the log's clock in the standard timestamp format. The server uses it for `server_time`.
- `parse_timestamp` is a public name for the timestamp parser that already exists.
- `get_human_actions` lists human clicks and drags together, oldest first. Mismatches are computed from the clicks only.

### detection.py

`detect_mismatches` first keeps only actions whose `kind` is `"click"`. The rest of the algorithm is unchanged. `detect_scale_problem` is unchanged.

### server.py

- One helper reads and validates a request body for both `/human-click` and `/agent-click`. It takes the actor as an argument. It accepts `x`, `y`, `coordinate_space`, `scale_factor`, optional `ui_element`, and optional `end_x` and `end_y`.
  - `end_x` and `end_y` both present: record a drag. Neither present: record a click. Exactly one: HTTP 400 `end_x and end_y must be given together`.
  - Not a number: HTTP 400 `Invalid field type`. All the base 400 reasons stay.
  - Success: `{"status": "recorded", "actor": ..., "kind": ..., "timestamp": ...}` and an INFO log `/human-click recorded ...` or `/agent-click recorded ...`.
- `GET /human-actions` returns the payload of the `get_human_actions` tool plus `server_time`. The `since` query parameter is passed through. A bad value gives HTTP 400 with the validation message. The route only reads.
- The `get_human_actions` tool result includes `kind`, `end_x`, `end_y` for each action.

## New modules

### activity.py

Pure functions on the dictionaries of the read route.

- `describe_action(action)`: `the human clicked (x, y) at HH:MM:SS UTC`, or `the human dragged from (x, y) to (x, y) at HH:MM:SS UTC`. When `ui_element` has a role, ` on a <role>` goes before ` at`. One decimal for coordinates.
- `describe_mismatch(mismatch)`: `the human's click at (x, y) came N.Ns after the agent's click at (x, y), offset (+dx, +dy): that click probably missed or did something the human did not want`. The offset is signed with one decimal.
- `describe_activity(payload)`: actions oldest first, then mismatches, then the scale problem sentence from Requirement 6.5. An empty payload gives an empty list.

### watch.py

- `fetch_human_actions(server, since=None, timeout=3.0)`: `GET {server}/human-actions` with `since` as a query parameter, returns the parsed JSON.
- `Watcher(fetch)`: `start()` stores the `server_time` of a first fetch as the cursor; `poll()` fetches with that cursor, moves the cursor to the last action's timestamp and returns `describe_activity(payload)`.
- `run(server, interval, out=None, sleep=time.sleep, max_polls=None)`: prints `poltergeist: watching <server> for human actions in the Simulator` once, then `poltergeist: <line>` for each item. When the server cannot be reached it prints one `cannot reach` line and keeps trying; when it comes back it prints one `reachable again` line.
- `main(argv=None)`: options `--server` (default `http://127.0.0.1:8000`) and `--interval` (default 0.5).

### claude_hook.py

- `is_simulator_tool(name)`: lower-cased name starts with `mcp__` and contains `ios_simulator`.
- `agent_gesture(tool_input)`: for `action` equal to `tap` return a click body from `x`, `y`; for `swipe` a drag body from `x`, `y`, `x2`, `y2`; for `touch_path` a click or a drag from the first and last point of `points` (a click when they are equal or there is one point). Every body has `coordinate_space` `device_points` and `scale_factor` 1.0. Anything else, or malformed input, returns `None`.
- `Server(base_url)`: `record_agent(body)` posts to `/agent-click`; `human_actions(since)` gets `/human-actions` with a 2 second timeout.
- `CursorStore(session_id, directory=None)`: one JSON file per session in the state directory, with `load()` and `save(cursor)`. The session id is reduced to letters, digits, `-` and `_`.
- `context_for(lines)`: the header sentence of Requirement 8.6 followed by `- <line>` lines.
- `handle_event(event, server, cursor)`: ignore other tools; record the agent's gesture if any (errors swallowed); fetch the human's actions since the cursor; on the first call save the server time and return nothing; otherwise save the last action's timestamp and return the context text, or nothing when there is nothing new.
- `main(stdin=None, stdout=None, environ=None)`: read the event JSON, build the objects from `POLTERGEIST_URL` and `POLTERGEIST_HOOK_STATE_DIR`, call `handle_event`, print the JSON of Requirement 8.6 when there is a context, and always return 0.

## Error handling

- HTTP routes answer 400 with `{"error": <message>}` for bad input and 500 with `{"error": "Internal server error"}` for unexpected failures, and log both.
- The hook and the watcher never raise to their caller.

## Testing

The provided tests are the acceptance tests: `tests/test_drags.py`, `tests/test_agent_endpoint.py` and `tests/test_awareness.py`.
