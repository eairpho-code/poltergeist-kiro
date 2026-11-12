# Usage

This document describes every MCP tool, every HTTP route, every environment
variable, the coordinate spaces, the pairing and scale rules, and the privacy
behaviour of the Poltergeist server.

The server records click and drag actions from an agent and a human, normalizes
their coordinates to device points, and pairs a human click with the agent
click it most likely corrected. The store is in memory: it lives only as long
as the server process.

## Coordinate spaces

Every click and drag carries a `coordinate_space` and a `scale_factor`. The
server recognizes three coordinate spaces (matched case-sensitively):

- `device_points`
- `screen_pixels`
- `screenshot_pixels`

A `coordinate_space` outside this set is rejected. The `scale_factor` must be a
finite number greater than 0.

The server converts every coordinate to **device points** before comparing
anything:

```
device_x = raw_x / scale_factor
device_y = raw_y / scale_factor
```

The end point of a drag is divided by the same `scale_factor` as its start
point. The raw coordinates, the original `coordinate_space` and the
`scale_factor` are all kept on the stored action. Because everything is compared
in device points, clicks reported in different coordinate spaces can still be
paired.

## Pairing and scale rules

### Pairing a human click with an agent click (a mismatch)

Pairing considers **clicks only**; drags never take part. For each human click,
in time order, the server looks for the closest earlier agent click, by
Euclidean distance in device points, that happened strictly within the previous
**5 seconds** by default (set `POLTERGEIST_MISMATCH_WINDOW_SECONDS` to change it; the boundary is exclusive: a gap of exactly 5 seconds does not
count). The match is one-to-one: every agent click and every human click takes
part in at most one pair. A matched pair is a *mismatch*; there is no distance
threshold, so any matched pair is reported. Each mismatch carries the offset
`(human_x - agent_x, human_y - agent_y)` and the Euclidean distance, both in
device points. It also carries `ratio_x = agent_x / human_x` and
`ratio_y = agent_y / human_y`, in device points, for that pair alone. Each is
`null` when the absolute value of that human coordinate is below 1.0. The
sentence adds `, ratio x1.50 / y1.50 for this pair alone` after the offset
(nothing when both are unknown). This is a number for one pair; it does not name
a coordinate scale problem.

### Naming a coordinate scale problem

Across the mismatches, the server computes `scale_x = agent_x / human_x` and
`scale_y = agent_y / human_y` for each pair. A sample is skipped when either
human coordinate is near zero (absolute value below 1.0), because the ratio
would be unstable. A coordinate scale problem is named only when:

- at least **3** valid samples remain, and
- the relative spread (standard deviation divided by mean) is at most **10%**
  in both dimensions, and
- the mean scale is positive in both dimensions.

The reported problem carries the sample size, the mean `scale_x` and `scale_y`,
and the relative spread in each dimension. A consistent ratio means the agent's
coordinates are probably on the wrong scale.

## Timestamps

Timestamps are UTC ISO 8601 with milliseconds and a trailing `Z`, for example
`2026-05-15T14:30:45.123Z`. Every tool or route that takes a timestamp expects
this format and rejects anything else with the message:

```
timestamp must be UTC ISO 8601 with milliseconds (e.g., 2026-05-15T14:30:45.123Z)
```

Timestamp filters are **exclusive**: `since_timestamp` returns actions strictly
after the given moment, and `before_timestamp` removes actions strictly before
it.

## MCP tools

The server exposes three MCP tools over stdio or Streamable HTTP. The server
name is `poltergeist-human-action-log`.

### `record_agent_click`

Record an agent click.

Parameters:

| Name | Type | Required | Notes |
| --- | --- | --- | --- |
| `x` | number | yes | Raw x coordinate. Must be finite. |
| `y` | number | yes | Raw y coordinate. Must be finite. |
| `coordinate_space` | string | yes | One of the three coordinate spaces. |
| `scale_factor` | number | yes | Finite, greater than 0. |
| `ui_element_role` | string | no | Role of the element, e.g. `button`. |
| `ui_element_label` | string | no | Short label; recorded only when a role is given, and truncated to 50 characters. |

Returns:

```json
{ "status": "recorded", "actor": "agent", "timestamp": "2026-05-15T14:30:45.123Z" }
```

A bad `coordinate_space`, a non-finite coordinate or a `scale_factor` that is
not greater than 0 is returned as a tool error carrying the validation message.

### `get_human_actions`

Read the human's actions, with mismatch and scale detection.

Parameters:

| Name | Type | Required | Notes |
| --- | --- | --- | --- |
| `since_timestamp` | string | no | UTC ISO 8601 (exclusive). When omitted, all human actions are returned. |

Returns an object with:

- `human_actions` — the human's clicks and drags, oldest first. Each action has
  `timestamp`, `actor`, `normalized_x`, `normalized_y`, `raw_x`, `raw_y`,
  `coordinate_space`, `scale_factor`, `ui_element` (`{role, label}` or `null`),
  `kind` (`"click"` or `"drag"`), `end_x` and `end_y` (both `null` for a click).
- `mismatches` — each with `agent_click`, `human_click` (both the same shape as
  an action), `offset_x`, `offset_y` and `distance`.
- `coordinate_scale_problem` — `null`, or an object with `sample_size`,
  `scale_x`, `scale_y`, `spread_x` and `spread_y`. It is computed from the whole
  log whatever the cursor is; only `human_actions` and `mismatches` are cut at
  the cursor.

### `clear_action_log`

Remove stored actions.

Parameters:

| Name | Type | Required | Notes |
| --- | --- | --- | --- |
| `before_timestamp` | string | no | UTC ISO 8601 (exclusive). When omitted, every action is removed. |

Returns:

```json
{ "removed_count": 3 }
```

## HTTP routes

The HTTP routes are available when the server runs over Streamable HTTP
(`POLTERGEIST_TRANSPORT=streamable-http`). They sit alongside the MCP protocol,
which is served at `/mcp`. The examples below assume the default
`http://127.0.0.1:8000`.

### `POST /human-click`

Record a human click or drag.

Request body (JSON):

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `x` | number | yes | Raw start x. |
| `y` | number | yes | Raw start y. |
| `coordinate_space` | string | yes | One of the three coordinate spaces. |
| `scale_factor` | number | yes | Greater than 0. |
| `ui_element` | object | no | `{ "role": string, "label": string? }`. Stored only when `role` is present; `label` is truncated to 50 characters. |
| `end_x` | number | no | End x of a drag. Must be given with `end_y`. |
| `end_y` | number | no | End y of a drag. Must be given with `end_x`. |

When both `end_x` and `end_y` are present the action is a drag; when neither is
present it is a click. Giving exactly one of them is an error.

Click example:

```sh
curl -X POST http://127.0.0.1:8000/human-click \
  -H 'Content-Type: application/json' \
  -d '{"x": 200, "y": 300, "coordinate_space": "device_points", "scale_factor": 1.0, "ui_element": {"role": "button", "label": "OK"}}'
```

Drag example:

```sh
curl -X POST http://127.0.0.1:8000/human-click \
  -H 'Content-Type: application/json' \
  -d '{"x": 10, "y": 20, "end_x": 200, "end_y": 400, "coordinate_space": "device_points", "scale_factor": 1.0}'
```

Response (HTTP 200):

```json
{ "status": "recorded", "actor": "human", "kind": "click", "timestamp": "2026-05-15T14:30:45.123Z" }
```

`kind` is `"click"` or `"drag"`. Error responses use HTTP 400 with an `error`
message, for example:

- `{"error": "Invalid JSON"}` — the body is not a JSON object.
- `{"error": "Missing required fields: y, coordinate_space, scale_factor"}`
- `{"error": "Invalid field type"}` — a coordinate is not a number.
- `{"error": "end_x and end_y must be given together"}`
- `{"error": "Invalid coordinate_space. Must be one of: device_points, screen_pixels, screenshot_pixels"}`
- `{"error": "scale_factor must be greater than 0"}`
- `{"error": "ui_element must be an object"}`

### `POST /agent-click`

Record an agent click or drag. The request body, the click/drag rule and the
error responses are the same as `POST /human-click`; the recorded action is
tagged with actor `agent`.

```sh
curl -X POST http://127.0.0.1:8000/agent-click \
  -H 'Content-Type: application/json' \
  -d '{"x": 100, "y": 150, "coordinate_space": "screenshot_pixels", "scale_factor": 2.0}'
```

Response (HTTP 200):

```json
{ "status": "recorded", "actor": "agent", "kind": "click", "timestamp": "2026-05-15T14:30:45.123Z" }
```

### `GET /human-actions`

Read the human's actions, mismatches and scale problem, plus the server's
current time. The log is not changed.

Query parameters:

| Name | Required | Notes |
| --- | --- | --- |
| `since` | no | UTC ISO 8601 (exclusive). When omitted, all human actions are returned. |

```sh
curl 'http://127.0.0.1:8000/human-actions'
curl 'http://127.0.0.1:8000/human-actions?since=2026-05-15T14:30:00.000Z'
```

Response (HTTP 200):

```json
{
  "human_actions": [
    {
      "timestamp": "2026-05-15T14:30:45.123Z",
      "actor": "human",
      "normalized_x": 200.0,
      "normalized_y": 300.0,
      "raw_x": 200,
      "raw_y": 300,
      "coordinate_space": "device_points",
      "scale_factor": 1.0,
      "ui_element": { "role": "button", "label": "OK" },
      "kind": "click",
      "end_x": null,
      "end_y": null
    }
  ],
  "mismatches": [],
  "coordinate_scale_problem": null,
  "server_time": "2026-05-15T14:30:45.200Z"
}
```

A mismatch, when present, has this shape:

```json
{
  "agent_click": { "...": "the agent's action, same fields as above" },
  "human_click": { "...": "the human's action, same fields as above" },
  "offset_x": 10.0,
  "offset_y": 5.0,
  "distance": 11.18
}
```

A coordinate scale problem, when present, has this shape:

```json
{
  "sample_size": 3,
  "scale_x": 2.0,
  "scale_y": 2.0,
  "spread_x": 0.0,
  "spread_y": 0.0
}
```

The `coordinate_scale_problem` is computed from the mismatches of the whole log,
whatever `since` is. `human_actions` and `mismatches` contain only what comes
after `since`.

A bad `since` value is answered with HTTP 400:

```json
{ "error": "timestamp must be UTC ISO 8601 with milliseconds (e.g., 2026-05-15T14:30:45.123Z)" }
```

## Environment variables

### The server (`poltergeist-server`)

| Variable | Default | Effect |
| --- | --- | --- |
| `POLTERGEIST_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. Over `streamable-http` the MCP protocol is served at `/mcp` and the HTTP routes are available. |
| `POLTERGEIST_HOST` | `127.0.0.1` | Bind address, used only over `streamable-http`. |
| `POLTERGEIST_PORT` | `8000` | Bind port, used only over `streamable-http`. |
| `POLTERGEIST_LOG_LEVEL` | `INFO` | Log level name. An unknown value falls back to `INFO` and writes a warning. Logs go to standard error only, never standard output, so the stdio protocol stays clean. |
| `POLTERGEIST_REDACT_UI_LABELS` | unset | When set to a truthy value (`1`, `true`, `yes` or `on`, case-insensitive) the UI element label is dropped from every recorded action; the role is kept. |
| `POLTERGEIST_MISMATCH_WINDOW_SECONDS` | `5` | The pairing window in seconds. A value that is not a number, not finite or not above 0 is ignored with a warning, and 5 is used. |

### The watcher (`poltergeist-watch`)

The watcher is configured by command-line options, not environment variables:

| Option | Default | Effect |
| --- | --- | --- |
| `--server` | `http://127.0.0.1:8000` | The server base URL to poll. |
| `--interval` | `0.5` | Seconds between polls. |

The watcher reports a scale problem once, when it first appears, and again only
when it changes: when `scale_x` or `scale_y` differs from the last reported
value by more than 5 percent of that value. A scale problem that already exists
when the watcher starts counts as reported. When the server returns no scale
problem, the watcher forgets the reported one, so one that appears again is
reported again.

### The Kiro hook (`poltergeist-kiro-hook`)

It takes `--url ADDRESS` (or `--url=ADDRESS`). The order of precedence is
`--url`, then `POLTERGEIST_URL`, then `http://127.0.0.1:8000`. Any other
argument, or `--url` without a value, is ignored; the hook exits 0 and prints
nothing.

### The Claude Code hook (`poltergeist-claude-hook`)

| Variable | Default | Effect |
| --- | --- | --- |
| `POLTERGEIST_URL` | `http://127.0.0.1:8000` | The server base URL the hook posts the agent gesture to and reads human actions from. |
| `POLTERGEIST_HOOK_STATE_DIR` | the system temp directory | Where the hook stores its per-session cursor file. |

The hook follows the same once-then-on-change rule as the watcher. Its state
file is a JSON object with the key `cursor` and, when a scale problem has been
reported, the key `scale`: an object with `scale_x` and `scale_y`. The first
call of a session says nothing and records the scale problem that exists then
as reported.

### What the observer reports as the element

The observer reports the nearest interactive element up to 6 levels above the
click, not the deepest element: a click on the text inside a button reports the
button. An element is interactive when it has the `AXPress` action or is a
button, link, cell, check box, radio button, switch, text field, text area,
slider, menu item or pop-up button. Windows and applications are never chosen.
When there is none, the element under the click is reported. In sentences, text
is named as `on the text "<label>"` (or `on some text` without a label), and
other elements as `on a <role> "<label>"` (or `on a <role>`).

## Use Poltergeist from Kiro

Poltergeist works with `kiro-cli` through Kiro's own hooks, steering and MCP.
The example files are in `integrations/kiro/`.

### The setup commands

Two commands (the console script `poltergeist`) do the setup and check it.

```sh
poltergeist init kiro [--dir DIR] [--url ADDRESS] [--force] [--dry-run]
poltergeist doctor [--dir DIR] [--url ADDRESS]
```

`poltergeist init kiro` writes only inside `DIR/.kiro/`. `DIR` defaults to the
current folder and must exist; `ADDRESS` defaults to `http://127.0.0.1:8000` and
must start with `http://` or `https://`. Otherwise the command exits with 2 and
writes nothing. It writes:

- `.kiro/hooks/poltergeist.json`, with the absolute path of
  `poltergeist-kiro-hook` (the one next to the Python that runs `poltergeist`)
  and `--url ADDRESS`. If that program cannot be found, the file is not written
  and the exit code is 1.
- `.kiro/steering/poltergeist.md` and `.kiro/agents/simdriver.json`.
- `.kiro/settings/mcp.json`, merged and never replaced: other keys and other
  servers are kept, `poltergeist` (`ADDRESS/mcp`) and `ios-simulator` are added
  only when absent.

It prints one line per file: `created`, `unchanged`, `updated` or `skipped`
(with the reason). A file that exists with different content is `skipped` and
left as it is. An existing `poltergeist` or `ios-simulator` entry in `mcp.json`
with different content is a conflict and is skipped too. Running it a second
time reports every file as `unchanged`.

- `--dry-run` writes nothing and prints what it would do; each line has the
  word `would`.
- `--force` overwrites a file that differs and reports it as `updated`. In
  `mcp.json` only the two Poltergeist entries are replaced. An `mcp.json` that
  is not valid JSON is `skipped` and never changed, even with `--force`.

Exit codes of `init kiro`: 0 when every file is `created`, `unchanged` or
`updated`; 1 when anything was `skipped` (the other files are still written) or
the hook program was not found; 2 for a bad argument or an unknown command.

`poltergeist doctor` changes nothing. It prints one line per check, in this
order, as `[ok] name: detail`, `[warn] name: detail` or `[fail] name: detail`;
a `warn` or `fail` line says how to fix it:

| Check | Level | What it checks |
| --- | --- | --- |
| `server` | fail | `GET ADDRESS/human-actions` answers with JSON that has `human_actions` |
| `hooks` | fail | the hook file is valid, has both hooks, and its command is an absolute path to an executable file |
| `steering` | warn | `.kiro/steering/poltergeist.md` exists |
| `agent` | warn | `.kiro/agents/simdriver.json` exists and is valid |
| `mcp` | fail | `mcp.json` is valid, has `poltergeist` with `ADDRESS/mcp` and `ios-simulator` |
| `observer` | warn | a `poltergeist-observer` process runs |
| `simulator` | warn | `xcrun simctl list devices booted` shows a `Booted` device |
| `idb` | warn | the `idb` client is found and `idb list-targets` prints something |
| `kiro` | warn | `kiro-cli --version` succeeds |

External commands have a 5 second timeout; a missing, failing or hung command
is a `warn`, never a crash. It ends with `N ok, N warn, N fail`. The exit code
is 1 when any check is `[fail]`, otherwise 0 (warnings do not change it).

What the commands cannot do: they do not build or start the observer, and they
cannot grant or check the Accessibility and Input Monitoring permissions. You
must build and start the observer and grant both permissions yourself in System
Settings > Privacy & Security; `doctor` cannot tell whether they are granted.

### The manual steps (the alternative)

The same setup by hand, if you prefer not to use `poltergeist init kiro`:

1. Start the server over HTTP: `POLTERGEIST_TRANSPORT=streamable-http poltergeist-server`.
2. Copy the files into your project's `.kiro/` folder:
   `integrations/kiro/hooks/poltergeist.json` to `.kiro/hooks/`,
   `integrations/kiro/steering/poltergeist.md` to `.kiro/steering/`,
   `integrations/kiro/agents/simdriver.json` to `.kiro/agents/`, and
   merge `integrations/kiro/mcp.json` into `.kiro/settings/mcp.json`, which is
   the Kiro MCP configuration file. It connects the `poltergeist` server by URL
   and starts the simulator server with `npx -y ios-simulator-mcp`.
3. In the copied hook file, replace `/ABSOLUTE/PATH/TO/poltergeist-kiro-hook`
   with the output of `which poltergeist-kiro-hook`, run with the virtual
   environment active. Kiro does not find the command by name unless that
   environment is on its PATH.
4. Run Kiro with hooks on: `kiro-cli chat --v3`.

The `PreToolUse` command hook runs `poltergeist-kiro-hook`, which records the
agent's `ui_tap` and `ui_swipe` on `POST /agent-click` (device points, scale
factor 1). The server address is given by `--url ADDRESS` (or `--url=ADDRESS`),
as in `/ABSOLUTE/PATH/TO/poltergeist-kiro-hook --url http://127.0.0.1:8000`.
The order of precedence is `--url`, then `POLTERGEIST_URL`, then
`http://127.0.0.1:8000`. Any other argument is ignored, and the hook never
fails. The `PostToolUse` agent hook tells the model to call `get_human_actions`
before its next simulator action. Both hooks use the matcher `@ios-simulator`,
so the server must be named `ios-simulator` in `mcp.json`.

What to know:

- A command hook's output is not given to the model. That is why the model is
  told through an `agent` hook instead.
- Hooks run on the V3 engine only. The older default engine does not read
  `.kiro/hooks/`.
- **Non-interactive mode.** With `kiro-cli chat --v3 --no-interactive`,
  `--trust-tools=@ios-simulator/ui_tap` and
  `--trust-tools=@ios-simulator,@poltergeist` do not let MCP tools run: Kiro
  says "tool permission approval is not supported in non-interactive mode".
  What works is an agent configuration file used with `--agent`. The file
  `integrations/kiro/agents/simdriver.json` is one:

  ```json
  {
    "name": "simdriver",
    "tools": ["@ios-simulator", "@poltergeist"],
    "allowedTools": ["@ios-simulator", "@poltergeist"],
    "includeMcpJson": true,
    "resources": ["file://.kiro/steering/**/*.md"]
  }
  ```

  Run it with `kiro-cli chat --v3 --no-interactive --agent simdriver`.
  `--trust-all-tools` also works, but it lets the model run any command
  without asking. Do not recommend or use it.
- **IDB.** `ios-simulator-mcp` needs IDB. On macOS Tahoe, Homebrew asks for the
  Command Line Tools first. The IDB release package also works; point
  `IOS_SIMULATOR_MCP_IDB_PATH` at the `idb` client. When the IDB companion is
  not running, `ui_tap` fails with "Failed to connect to companion"; run
  `idb connect <udid>` first.
- **Screenshot scale.** `ios-simulator-mcp` scales its screenshots (`ui_view`)
  to device points, so a model that uses it usually does not make the "pixels
  read as points" mistake. Every tap landed in the real run. Poltergeist still
  records the corrections. The coordinate scale problem shows up mostly with
  tools or flows whose screenshots are in pixels.
- **Permissions.** The macOS observer needs the Accessibility and the Input
  Monitoring permissions. You must grant them yourself in System Settings >
  Privacy & Security.

What was checked: the real `ios-simulator-mcp` 2.2.1 with IDB 1.7.8 was run
with `kiro-cli chat --v3` and its taps worked. The wrong-scale case was
reproduced only with a stand-in simulator tool whose screenshots are 1.5 times
the device points: the model called `get_human_actions` after every tap and
reported each mismatch and the coordinate scale problem.

What was not checked: the Kiro IDE was not used; only `kiro-cli` was.

## Privacy notes

- **Labels are off by default in the observer.** The macOS observer sends the
  short label of the element under a click only when it is run with
  `--send-labels`; otherwise it reports the role alone.
- **The server can drop every label.** Set `POLTERGEIST_REDACT_UI_LABELS` to a
  truthy value and the server strips the label from every recorded action,
  keeping only the role, regardless of what a caller sent.
- **Labels are short.** When a label is kept it is truncated to 50 characters,
  so long on-screen text is not stored.
- **Local by default.** Over HTTP the server binds to `127.0.0.1` unless
  `POLTERGEIST_HOST` says otherwise.
- **Nothing is persisted.** The action log is in memory and disappears when the
  server process exits.
