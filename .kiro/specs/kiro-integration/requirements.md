# Requirements Document

## Introduction

Poltergeist tells an agent which clicks a human made for it. Today the command that feeds the human's actions back into the agent is made for Claude Code (`poltergeist/claude_hook.py`). This feature makes Poltergeist usable from Kiro with Kiro's own features: hooks, steering and MCP.

- A recorder command, `poltergeist-kiro-hook`, reads a Kiro hook event and records the agent's simulator tap or swipe on the server.
- A `PostToolUse` agent hook tells the model to call `get_human_actions` before its next simulator action. Kiro does not give the model what a command hook prints, so the model is told through an `agent` hook, not through output.
- Example files (hooks, MCP configuration, steering) and documentation let a user set this up step by step.

What was checked on a real Kiro (`kiro-cli chat --v3`): a model drove a stand-in simulator MCP server with `ui_tap`; a `PreToolUse` command hook posted each tap to `POST /agent-click`; a `PostToolUse` agent hook made the model call `get_human_actions`; a script posted a human click after each tap. The model reported each mismatch and, after the third tap, the coordinate scale problem.

What was NOT checked: the real simulator MCP server (`ios-simulator-mcp`; its tool names and arguments come from its public README and have not been run) and the Kiro IDE (only `kiro-cli` was used).

## Glossary

- **Event**: the one JSON object that Kiro writes to the standard input of a command hook. It has `session_id`, `hook_event_name`, `cwd`, `tool_name` and `tool_input`; a `PostToolUse` event also has `tool_response`.
- **Recorder**: the command `poltergeist-kiro-hook`, the module `poltergeist/kiro_hook.py`.
- **Simulator tool**: an MCP tool of the iOS simulator server. Only a tap (`ui_tap`) and a swipe (`ui_swipe`) are recorded.
- **Tool name**: for an MCP tool, `mcp_` + the server name + `_` + the tool name, with the hyphens of the server name turned into underscores.
- **Example files**: the files in `integrations/kiro/` that a user copies.
- **Server**: the Poltergeist server, reached over HTTP at the address in `POLTERGEIST_URL` (default `http://127.0.0.1:8000`).

## Requirements

### Requirement 1: Recognize a tap

**User Story:** As a user of Kiro, I want the agent's simulator taps to be recorded, so that Poltergeist can compare them with the human's clicks.

#### Acceptance Criteria

1. WHEN the lower-cased tool name ends with `ui_tap` and `tool_input` has numeric `x` and `y`, THE Recorder SHALL send `POST /agent-click` with a body of `x`, `y`, `coordinate_space` `"device_points"` and `scale_factor` `1`.
2. THE Recorder SHALL ignore every other field of `tool_input` (such as `duration` and `udid`).
3. THE Recorder SHALL treat the name case-insensitively and SHALL accept any server name, so `mcp_ios_simulator_ui_tap`, `@ios-simulator/ui_tap` and `mcp__ios-simulator__ui_tap` are all taps.
4. THE Recorder SHALL treat the same way an event of `PreToolUse` and of `PostToolUse`.
5. Integers and floats SHALL be sent as they are.

### Requirement 2: Recognize a swipe

**User Story:** As a user of Kiro, I want the agent's swipes to be recorded as drags, so that a swipe is not mistaken for a click.

#### Acceptance Criteria

1. WHEN the lower-cased tool name ends with `ui_swipe` and `tool_input` has numeric `x_start`, `y_start`, `x_end` and `y_end`, THE Recorder SHALL send `POST /agent-click` with `x` = `x_start`, `y` = `y_start`, `end_x` = `x_end`, `end_y` = `y_end`, `coordinate_space` `"device_points"` and `scale_factor` `1`.
2. THE Recorder SHALL ignore `duration`, `delta` and `udid`.

### Requirement 3: Ignore everything else, including bad input

**User Story:** As a user of Kiro, I want the recorder to record only what it understands, so that a screenshot or a malformed event never produces a false click.

#### Acceptance Criteria

1. A tool that is neither a tap nor a swipe SHALL be ignored: no request is sent.
2. A missing, non-string or non-matching `tool_name` SHALL be ignored.
3. A missing or non-object `tool_input` SHALL be ignored.
4. IF a required coordinate is missing, `null`, a string or a boolean, THEN THE Recorder SHALL ignore the event. A boolean and a string are not numbers. Non-finite numbers SHALL also be ignored.
5. Standard input that is empty, is not JSON or is JSON that is not an object SHALL be ignored.

### Requirement 4: Never fail and never hang the agent

**User Story:** As a user of Kiro, I want the recorder never to get in the way of the agent, so that a server that is down costs nothing.

#### Acceptance Criteria

1. THE Recorder SHALL exit with code 0 in every case, including any exception, a bad input and an unreachable server.
2. THE Recorder SHALL print nothing, on standard output or standard error.
3. EACH request SHALL have a timeout of at most 2 seconds, so that a slow server delays the agent by about 2 seconds at most.
4. THE Recorder SHALL use the standard library only.
5. THE server address SHALL come from `POLTERGEIST_URL`, default `http://127.0.0.1:8000`, as in `claude_hook.py`; a trailing slash SHALL not matter.

### Requirement 5: Run as a command

**User Story:** As a user, I want a command that Kiro can run in a hook, so that I do not write a script.

#### Acceptance Criteria

1. THE module `poltergeist/kiro_hook.py` SHALL define `main()` and SHALL run with `python -m poltergeist.kiro_hook`.
2. THE `pyproject.toml` SHALL define the console script `poltergeist-kiro-hook = "poltergeist.kiro_hook:main"`.
3. THE existing modules, tests and behaviour SHALL not change.

### Requirement 6: Example files for a user

**User Story:** As a user, I want files to copy into my project, so that I set up Kiro in a few minutes.

#### Acceptance Criteria

1. `integrations/kiro/hooks/poltergeist.json` SHALL be `{"version": "v1", "hooks": [...]}` with exactly two hooks, each with a `name`, a `trigger`, a `matcher` and an `action`.
2. THE first hook SHALL be a `PreToolUse` hook with a `command` action running `poltergeist-kiro-hook`.
3. THE second hook SHALL be a `PostToolUse` hook with an `agent` action whose prompt tells the model to call `get_human_actions` before its next simulator action.
4. BOTH hooks SHALL have the same matcher for the simulator server, written `@ios-simulator`.
5. `integrations/kiro/mcp.json` SHALL define `mcpServers.poltergeist` by a `url` ending in `/mcp`, and `mcpServers.ios-simulator` through `npx -y ios-simulator-mcp`.
6. `integrations/kiro/steering/poltergeist.md` SHALL tell the model what the hook prompt means, to use `since_timestamp` with the latest human action time it has already seen, and what to do with a mismatch and with a coordinate scale problem.

### Requirement 7: Documentation

**User Story:** As a user, I want to know how to set this up and how far to trust it.

#### Acceptance Criteria

1. THE `README.md` and `docs/usage.md` SHALL each have a section about Kiro.
2. THE sections SHALL give the steps: start the server over HTTP, copy the files from `integrations/kiro/`, run Kiro with hooks on (`kiro-cli chat --v3`).
3. THE sections SHALL say what was checked and what was not: the real `ios-simulator-mcp` was not run and the Kiro IDE was not used.
4. THE sections SHALL say that a command hook's output is not given to the model, and that the older default engine does not read `.kiro/hooks/`.

### Requirement 8: Tests

**User Story:** As a maintainer, I want tests, so that the recorder and the example files stay correct.

#### Acceptance Criteria

1. `tests/test_kiro_hook.py` SHALL test the recorder: a tap, a swipe, every ignored case of Requirement 3, the exit code and silence of Requirement 4, and the address from `POLTERGEIST_URL`.
2. THE tests SHALL also check the shape of the example files of Requirement 6.
3. THE tests SHALL not need Kiro, Node.js or a simulator.
