# Poltergeist

Poltergeist is an MCP server that tells an AI agent which clicks a human made
for it.

When an agent drives an iOS Simulator it clicks by coordinate. If its
coordinates are off, the click lands in the wrong place and a human reaches over
and clicks where the agent meant to. Poltergeist records both clicks. It pairs a
human click with the agent click it most likely corrected: the closest earlier
agent click within the preceding five seconds. The offset between the two is the
agent's error. When several such corrections share the same ratio between the
agent's coordinates and the human's, Poltergeist names a *coordinate scale
problem*: the agent's coordinates are probably on the wrong scale (for example a
retina screenshot read as if it were device points). The agent can then read
back what the human did and correct itself.

All coordinates are normalized to device points before anything is compared, so
clicks reported in screenshot pixels, screen pixels or device points can be
paired with each other.

## What is in the box

- An MCP server (`poltergeist-server`) with three tools and three HTTP routes plus the MCP endpoint at `/mcp`.
- A watcher (`poltergeist-watch`) that prints a line for each human action.
- A Claude Code hook (`poltergeist-claude-hook`) that feeds the human's recent
  actions back into the agent after each simulator tool call.
- A macOS observer (`observer/`) that watches the real mouse over an iOS
  Simulator and reports clicks and drags to the server.
- A browser demo (`demo/index.html`) that re-implements the detection rules in
  JavaScript and tells the story with a scripted agent.

## Install and run

Poltergeist needs Python 3.11 or newer. Clone this repository, create a virtual
environment and install the package into it:

```sh
python3 -m venv venv
source venv/bin/activate
pip install .
```

Install the test dependencies as well with `pip install ".[dev]"`.

The server reads its transport from environment variables. By default it speaks
the MCP protocol over stdio:

```sh
poltergeist-server
```

To serve over Streamable HTTP instead, set `POLTERGEIST_TRANSPORT`:

```sh
POLTERGEIST_TRANSPORT=streamable-http poltergeist-server
```

Over HTTP the server binds to `POLTERGEIST_HOST` (default `127.0.0.1`) and
`POLTERGEIST_PORT` (default `8000`). The MCP protocol is served at the `/mcp`
path; the plain HTTP routes below sit next to it.

You can also run the server without installing the package:

```sh
python poltergeist/server.py
```

## Connect Claude Code

With the server running over Streamable HTTP, register it with Claude Code:

```sh
claude mcp add --transport http poltergeist http://127.0.0.1:8000/mcp
```

The agent then has the `record_agent_click`, `get_human_actions` and
`clear_action_log` tools.

## Tools and routes

Three MCP tools:

- `record_agent_click(x, y, coordinate_space, scale_factor, ui_element_role=None, ui_element_label=None)`
  records an agent click and returns `{status, actor, timestamp}`.
- `get_human_actions(since_timestamp=None)` returns the human's actions, the
  mismatches and any coordinate scale problem.
- `clear_action_log(before_timestamp=None)` removes stored actions and returns
  `{removed_count}`.

Three HTTP routes plus the MCP endpoint at `/mcp`:

- `POST /human-click` records a human click or drag.
- `POST /agent-click` records an agent click or drag.
- `GET /human-actions` reads the human's actions, mismatches and scale problem,
  plus the server's current time.

The request and response fields of every tool and route are documented in
[`docs/usage.md`](docs/usage.md).

## The macOS observer

The observer watches the Mac mouse and reports clicks and drags that land on an
iOS Simulator display. It is a Swift package in `observer/`, built for macOS 13
or newer.

Build it with Swift:

```sh
cd observer
swift build -c release
```

The binary is written to `observer/.build/release/poltergeist-observer`. Run it:

```sh
.build/release/poltergeist-observer
```

Options:

- `--server URL` — the server base URL (http or https with a host). Default
  `http://127.0.0.1:8000`.
- `--send-labels` — include the short label of the element under a click. Off by
  default for privacy.
- `--agent-app NAME` — treat synthetic clicks from this app (process name, app
  name or bundle identifier) as the agent's. May be given more than once.
- `--include-synthetic` — count synthetic clicks that match no agent app as the
  human's instead of ignoring them.
- `--dry-run` — print each gesture to standard output and do not contact the
  server.
- `--verbose` — also log why a gesture was ignored (for debugging).
- `-h`, `--help` — print help and exit.

The observer needs both the **Accessibility** and the **Input Monitoring**
permissions in System Settings > Privacy & Security. Without them it cannot
watch the mouse or read the Simulator display and exits with an error.

An agent that moves the real mouse makes synthetic clicks. Name that program
with `--agent-app` so its clicks are recorded as the agent's (`POST
/agent-click`) rather than the human's. Clicks the observer cannot attribute to
a named agent app are treated as the human's only when `--include-synthetic` is
set; otherwise they are ignored. The observer reports in device points with a
scale factor of 1.

The element it reports for a click is the nearest interactive element up to 6
levels above the click, so a click on the text inside a button reports the button.

## How an agent hears about human actions

There are three ways an agent learns what the human did:

- **The `get_human_actions` tool.** The agent calls it directly over MCP and
  reads the human actions, mismatches and scale problem out of the result.
- **`poltergeist-watch`.** This command polls `GET /human-actions` and prints a
  sentence for each new human action, mismatch and scale problem. It starts from
  the server's current time, so it never replays history, and it keeps trying
  when the server is unreachable.

  ```sh
  poltergeist-watch --server http://127.0.0.1:8000 --interval 0.5
  ```

  Both options have the defaults shown.

- **The Claude Code hook.** `poltergeist-claude-hook` runs after each tool call.
  When the tool is the iOS simulator it records the agent's gesture on the
  server and then reports the human's actions since the agent's previous
  simulator action, as additional context, so the agent knows the screen may
  have moved under it. The hook never fails the agent: on any error it exits
  quietly with code 0.

  Wire it into Claude Code with a `PostToolUse` hook in `settings.json`:

  ```json
  {
    "hooks": {
      "PostToolUse": [
        {
          "matcher": "mcp__.*[Ss]imulator.*",
          "hooks": [
            { "type": "command", "command": "poltergeist-claude-hook" }
          ]
        }
      ]
    }
  }
  ```

  Point the hook at a non-default server with the `POLTERGEIST_URL` environment
  variable.

## The demo

Open `demo/index.html` in a browser. It is a self-contained page: a JavaScript
port of the detection rules, driving a scripted agent that clicks a mock phone
app with a coordinate bug, so you can watch a human correct the agent and see
the mismatch and scale problem named.

Two checks confirm the JavaScript stays faithful to the Python code (both need
Node.js, run from the repository root):

```sh
python demo/check_port.py   # the JS detection matches the Python detection
python demo/check_app.py    # the phone mini-app behaves as the page describes
```

## Tests

Run every test from the repository root:

```sh
# Python tests (needs the dev dependencies)
pytest

# Swift tests for the observer
cd observer && swift test

# Demo parity checks (need Node.js)
python demo/check_port.py
python demo/check_app.py
```

## Repository map

```
poltergeist/            The Python package
  server.py             MCP server: the three tools and three HTTP routes plus /mcp
  action_log.py         In-memory action log, data models, timestamps
  detection.py          Mismatch and coordinate-scale-problem detection
  normalize.py          Coordinate normalization to device points
  activity.py           Turns actions into short English sentences
  watch.py              poltergeist-watch
  claude_hook.py        poltergeist-claude-hook
  logging_config.py     Logging to stderr
observer/               The macOS Swift observer
  Sources/              poltergeist-observer executable and ObserverCore
  Tests/                Swift tests
demo/                   The browser demo
  index.html            The page (JavaScript port and scripted agent)
  check_port.py         Detection parity check (needs Node.js)
  check_app.py          Phone mini-app check (needs Node.js)
docs/
  usage.md              Every tool, route and environment variable
  mcp_sdk_reference.md  Verified facts about the MCP Python SDK
tests/                  The Python test suite
.kiro/specs/            The specifications, each with requirements, design and tasks:
  human-action-log/     The base feature (clicks, pairing, scale problem)
  agent-awareness/      Drags, agent clicks over HTTP, watcher and hook
  simulator-observer/   The macOS observer
  browser-demo/         The browser demo
```
