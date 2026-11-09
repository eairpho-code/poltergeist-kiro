# Requirements Document

## Introduction

The Human Action Log records clicks and tells an agent which clicks a human made. This feature extends it so that an agent notices what a person does while it works:

- a press-move-release (a swipe, a scroll, a slider move) is recorded as a drag, not only as a click;
- an agent that moves the real mouse can report its own clicks over HTTP;
- the human's actions can be read over HTTP, streamed as lines, and fed into a Claude Code session after each simulator action.

All coordinates are normalized to device points, as in the base feature.

## Glossary

- **Click**: a single press at one point. Its kind is `"click"` and it has no end point.
- **Drag**: a press at a start point and a release at an end point. Its kind is `"drag"`.
- **Gesture**: a click or a drag.
- **Read route**: the HTTP route `GET /human-actions`.
- **Watcher**: a command that prints one line for each new human action.
- **Hook**: a command that Claude Code runs after each simulator tool call.

## Requirements

### Requirement 1: Record drags

**User Story:** As an agent, I want to know when the human dragged on the screen, so that I understand why the screen changed.

#### Acceptance Criteria

1. THE ClickAction SHALL carry `kind` (`"click"` by default or `"drag"`), `end_x` and `end_y`; a click SHALL have `end_x` and `end_y` equal to `None`.
2. THE ActionLog SHALL provide `record_human_drag(x, y, end_x, end_y, coordinate_space, scale_factor, ui_element=None)` and `record_agent_drag` with the same arguments, each returning the recorded action with kind `"drag"`.
3. THE end point SHALL be normalized with the same scale factor as the start point, and the raw start coordinates SHALL be kept.
4. IF an end coordinate is not finite, THEN the ActionLog SHALL raise `ValueError` containing `end_x and end_y must be finite` and SHALL record nothing.
5. A drag SHALL keep the role and label of its UI element.
6. WHEN human actions are listed, human drags SHALL appear with the clicks, oldest first. Agent drags SHALL NOT appear.
7. THE `get_human_actions` MCP tool result SHALL include `kind`, `end_x` and `end_y` for every action.

### Requirement 2: Drags never take part in pairing

**User Story:** As an agent, I want only clicks to be paired as corrections, so that a swipe is not mistaken for a missed click.

#### Acceptance Criteria

1. THE mismatch detection SHALL consider clicks only. A human drag SHALL NOT be paired with an agent click, and an agent drag SHALL NOT be paired with a human click.
2. A drag that lies between an agent click and a human click SHALL NOT stop those two clicks from pairing.

### Requirement 3: Drags over HTTP

**User Story:** As an observer program, I want to report a drag with one request, so that I do not need a second endpoint.

#### Acceptance Criteria

1. WHEN a `POST /human-click` body contains both `end_x` and `end_y`, THE server SHALL record a human drag; otherwise it SHALL record a human click.
2. THE response SHALL include `kind`, besides `status`, `actor` and `timestamp`.
3. IF only one of `end_x` and `end_y` is given, THEN the server SHALL answer HTTP 400 with an error containing `end_x and end_y must be given together` and SHALL record nothing.
4. IF an end coordinate is not a number, THEN the server SHALL answer HTTP 400 with an error containing `Invalid field type`.
5. THE end coordinates SHALL be normalized with the request's `scale_factor`.

### Requirement 4: Agent clicks over HTTP

**User Story:** As a program that moves the real mouse for an agent, I want to report the agent's clicks over HTTP, so that a human correction can be paired with them.

#### Acceptance Criteria

1. THE server SHALL provide `POST /agent-click` that accepts the same body as `POST /human-click`, including optional `ui_element` and optional `end_x` and `end_y`, and records the action with actor `"agent"`.
2. THE response SHALL contain `status` equal to `"recorded"`, `actor`, `kind` and `timestamp`.
3. THE same validation and the same HTTP 400 reasons as `POST /human-click` SHALL apply, and a rejected request SHALL record nothing.
4. A body that is not valid JSON or not a JSON object SHALL be answered with HTTP 400.
5. THE server SHALL log each recorded agent click at INFO level with a message containing `/agent-click recorded`.
6. Agent clicks SHALL NOT appear as human actions, and a human click that follows an agent click recorded this way SHALL be reported as a mismatch.

### Requirement 5: Read the human's actions over HTTP

**User Story:** As a watcher or hook, I want to read the human's actions with a plain HTTP request, so that I do not need an MCP session.

#### Acceptance Criteria

1. THE server SHALL provide `GET /human-actions` returning the same `human_actions`, `mismatches` and `coordinate_scale_problem` as the `get_human_actions` tool, plus `server_time`, the server clock's current time as UTC ISO 8601 with milliseconds and a trailing `Z`.
2. WHEN the query parameter `since` is given, THE route SHALL return only actions after that timestamp.
3. IF `since` is not a UTC ISO 8601 timestamp, THEN the route SHALL answer HTTP 400 with an error containing `timestamp must be UTC ISO 8601`.
4. THE route SHALL NOT change the log.

### Requirement 6: Describe human actions in words

**User Story:** As an agent, I want the human's actions as short sentences, so that I can read them without parsing JSON.

#### Acceptance Criteria

1. THE module `poltergeist.activity` SHALL provide `describe_action`, `describe_mismatch` and `describe_activity`, working on the dictionaries that the read route returns.
2. A click SHALL be described as `the human clicked (x, y) at HH:MM:SS UTC`, and as `the human clicked (x, y) on a <role> at HH:MM:SS UTC` when the element role is known. Coordinates SHALL have one decimal.
3. A drag SHALL be described as `the human dragged from (x, y) to (x, y) at HH:MM:SS UTC`, with the same optional role.
4. A mismatch SHALL say how many seconds after the agent's click the human clicked, with one decimal, both positions, and the signed offset, and SHALL end with `that click probably missed or did something the human did not want`.
5. A coordinate scale problem SHALL be described as `the agent's clicks miss by a consistent factor of about x<scale_x> horizontally and x<scale_y> vertically (<n> samples): its coordinates are probably on the wrong scale`, with two decimals.
6. `describe_activity` SHALL return the human actions oldest first, then the mismatches, then the scale problem; it SHALL return no lines when there is nothing to report.

### Requirement 7: Watch the human's actions

**User Story:** As someone running an agent, I want a command that prints a line for each human action, so that the agent can follow them while it works.

#### Acceptance Criteria

1. THE module `poltergeist.watch` SHALL provide `Watcher`, `fetch_human_actions`, `run` and `main`, and a command `poltergeist-watch` with options `--server` and `--interval`.
2. THE Watcher SHALL start from the server's current time, so history is not reported.
3. THE Watcher SHALL report each human action once, including drags and the mismatch that a click causes.
4. THE command SHALL print one line per item, starting with `poltergeist: `, and SHALL keep trying when the server is unreachable.

### Requirement 8: Tell the agent after each simulator action

**User Story:** As an agent running in Claude Code, I want to hear what the human did after each of my simulator actions, so that I do not act on a screen that has changed.

#### Acceptance Criteria

1. THE module `poltergeist.claude_hook` SHALL provide `is_simulator_tool`, `agent_gesture`, `Server`, `CursorStore`, `handle_event` and `main`, and a command `poltergeist-claude-hook`.
2. A tool is the simulator tool only when its name starts with `mcp__` and contains `ios_simulator`, ignoring case.
3. A `tap` becomes an agent click and a `swipe` or a `touch_path` becomes an agent drag, in device points with scale factor 1. A touch path that starts and ends at the same point is a click. Other actions and malformed input become nothing.
4. THE hook SHALL record the agent's gesture on the server through `POST /agent-click`.
5. THE hook SHALL ask the server for the human's actions since the last call of the same session. On the first call of a session it SHALL say nothing and only remember the server time.
6. WHEN there are new human actions, THE hook SHALL print JSON of the shape `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": <text>}}`, where the text starts with `Poltergeist: since your last simulator action, the human also acted in the Simulator, so the screen may not be where you left it:` followed by one `- <line>` per item.
7. EACH human action SHALL be reported only once, and the agent's own gestures SHALL NOT be reported back to it.
8. SESSIONS SHALL keep separate cursors, stored per session in a state directory (`POLTERGEIST_HOOK_STATE_DIR`, default the system temp directory). THE server address SHALL come from `POLTERGEIST_URL`, default `http://127.0.0.1:8000`.
9. THE hook SHALL NEVER fail or hang the agent: an unreachable server, bad input on stdin, or any other error SHALL end quietly with exit code 0 and no output. Other tools SHALL be ignored without contacting the server.

### Requirement 9: Install and document

**User Story:** As a user, I want to install the package and find the commands and routes documented.

#### Acceptance Criteria

1. THE package configuration SHALL define the commands `poltergeist-server`, `poltergeist-watch` and `poltergeist-claude-hook`.
2. THE README SHALL explain what the project does, how to install and run it, how to connect it to Claude Code, the tools and routes, and how the click observer fits in.
3. THE docs SHALL describe every HTTP route and every environment variable, with a request example for each route.
