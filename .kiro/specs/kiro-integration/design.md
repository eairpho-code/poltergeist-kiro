# Design Document

## Overview

This design adds one module, `poltergeist/kiro_hook.py`, one console script, a folder of example files, tests and documentation. It changes no existing module. Kiro runs the recorder before a simulator tool call; the model is told to read the human's actions by an agent hook and by steering.

```
 Kiro (kiro-cli chat --v3)
   │  PreToolUse, matcher @ios-simulator
   ├─ command hook ─▶ poltergeist-kiro-hook ──POST /agent-click──▶ ┐
   │                    (reads one event on stdin)                  ├─ Poltergeist server (HTTP)
   │  PostToolUse, matcher @ios-simulator                           │     one action log
   └─ agent hook ──▶ prompt to the model ─▶ get_human_actions ─────┘
                                              (MCP, url .../mcp)
```

The recorder and the MCP tool talk to the same server process, so they see the same log.

## Facts about Kiro that the design relies on

These were checked on a real Kiro, V3 engine (`kiro-cli chat --v3`).

- Hooks are JSON files in `.kiro/hooks/`: `{"version": "v1", "hooks": [{"name", "trigger", "matcher", "action"}]}`. An action is `{"type": "command", "command": "..."}` or `{"type": "agent", "prompt": "..."}`.
- The matcher `@<server>` matches every tool of the MCP server `<server>`, the name as written in `mcp.json`.
- A command hook gets one JSON object on standard input: `session_id`, `hook_event_name`, `cwd`, `tool_name`, `tool_input`, and for `PostToolUse` also `tool_response` (a string). The tool name is `mcp_` + server name + `_` + tool name, hyphens of the server name turned into underscores.
- What a command hook prints is NOT given to the model. Nothing here depends on it, which is why the recorder prints nothing.
- An `agent` action on `PostToolUse` IS given to the model, after the tool call.
- The older default engine does not read `.kiro/hooks/`.

Not checked: the real `ios-simulator-mcp` server (`ui_tap(x, y, duration?, udid?)` and `ui_swipe(x_start, y_start, x_end, y_end, duration?, delta?, udid?)`, from its README, device points) and the Kiro IDE.

## The recorder: poltergeist/kiro_hook.py

Standard library only (`json`, `math`, `os`, `sys`, `urllib.request`).

- `main() -> None`: reads standard input, calls `gesture_from_event`, and if a body comes back, calls `post_agent_click`. The whole body of `main` is wrapped in `except BaseException` so that nothing escapes; it returns normally, so the exit code is 0. It writes nothing to standard output or standard error.
- `gesture_from_event(text) -> dict | None`: pure. Parses the text as JSON; anything that is not an object gives `None`. Takes `tool_name` (must be a `str`) and `tool_input` (must be a `dict`).
  - lower-cased name ends with `ui_tap`: needs `x`, `y` → `{"x", "y", "coordinate_space": "device_points", "scale_factor": 1}`.
  - lower-cased name ends with `ui_swipe`: needs `x_start`, `y_start`, `x_end`, `y_end` → the same with `x`, `y`, `end_x`, `end_y`.
  - otherwise `None`.
- `_number(value)`: true only for an `int` or `float` that is not a `bool` and is finite. Strings, booleans, `None`, lists and NaN or infinity are rejected.
- `post_agent_click(base_url, body, timeout=2.0)`: `POST {base_url}/agent-click` with a JSON body, using `urllib.request` with the timeout. The response is read and dropped. Any error is the caller's to swallow.
- The base URL is `os.environ.get("POLTERGEIST_URL", "http://127.0.0.1:8000")` with a trailing slash removed.
- `if __name__ == "__main__": main()` makes `python -m poltergeist.kiro_hook` work.

Why a swipe uses `end_x`/`end_y`: the existing `POST /agent-click` already accepts a drag when both are given, so the server needs no change.

Why the timeout is 2 seconds and covers the whole request: `urllib` applies the timeout to each socket operation, and the server may answer slowly. One request, one timeout, no retry: the agent must never wait long for a log entry.

Why `PreToolUse`: the recorder runs before the tool call, so the agent click is stamped before the human can correct it. The recorder does not look at `hook_event_name`, so the same command also works on `PostToolUse`.

## Console script

`pyproject.toml` gets `poltergeist-kiro-hook = "poltergeist.kiro_hook:main"` next to the existing scripts.

## Example files: integrations/kiro/

- `hooks/poltergeist.json`: two hooks, both with the matcher `@ios-simulator`.
  - `poltergeist-record-agent-tap`, `PreToolUse`, `{"type": "command", "command": "poltergeist-kiro-hook"}`.
  - `poltergeist-check-human-actions`, `PostToolUse`, `{"type": "agent", "prompt": ...}`. The prompt names `get_human_actions` and says: before the next simulator action, call it, pass `since_timestamp` with the latest human action time already seen, and act on a mismatch or a coordinate scale problem.
- `mcp.json`: `{"mcpServers": {"poltergeist": {"url": "http://127.0.0.1:8000/mcp"}, "ios-simulator": {"command": "npx", "args": ["-y", "ios-simulator-mcp"]}}}`. The server name `ios-simulator` is the one the matcher uses.
- `steering/poltergeist.md`: short guidance for the model: what the hook prompt means, to use `since_timestamp`, and what to do with a mismatch (the human's click shows where the agent meant to click; use that point, not the agent's) and with a coordinate scale problem (divide coordinates by the reported ratio, then check with the next click).

## Documentation

- `README.md`: a section "Use Poltergeist from Kiro" with the steps and an honest list of what was and was not checked.
- `docs/usage.md`: a section with the recorder's contract (inputs, ignored cases, exit code, environment variable) and the same steps.

## Testing strategy

`tests/test_kiro_hook.py`, plain `pytest`, no Kiro, no Node.js and no simulator.

- Unit tests of `gesture_from_event`: tap, tap with floats, swipe, name variants, every ignored case.
- Tests of `main` as a subprocess (`python -m poltergeist.kiro_hook`) against a tiny local HTTP server that records requests: the body and path, exit code 0, empty output, `POLTERGEIST_URL`, an unreachable server, a slow server (the run ends in a few seconds).
- Shape tests of the example files: valid JSON, the hook fields, the shared matcher, the `/mcp` URL, the steering text, the console script in `pyproject.toml`.

## Error handling

| Situation | Behaviour |
|---|---|
| Bad or empty input | ignored, exit 0, no output |
| Not a tap or swipe | ignored |
| Non-numeric coordinate | ignored |
| Server unreachable or slow | request fails or times out after 2 s, swallowed, exit 0 |
| Any exception | swallowed, exit 0 |
