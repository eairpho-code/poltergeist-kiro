# Requirements Document

## Introduction

Poltergeist was run end to end on a real Mac: the iOS Simulator, the observer, the real simulator MCP server (`ios-simulator-mcp` 2.2.1 with IDB 1.7.8), `kiro-cli chat --v3` with the Kiro example files, and a human correcting with a real mouse. The run showed five things to fix.

1. In two runs the model got only one human correction before it had to act. The coordinate scale problem needs at least 3 samples, so it stayed `null`, and the model worked out the ratio by hand. Each mismatch now carries the ratio of its own pair.
2. Human corrections came 1.1 to 4.7 seconds after the agent's click, close to the 5 second limit, and the Kiro recorder runs before the tool, so a slow tool lengthens the gap. The pairing window is now configurable.
3. Kiro could not find `poltergeist-kiro-hook` unless the virtual environment was on its PATH, and the server address had to come from an environment variable. The recorder now takes the address as an argument and the example shows an absolute path.
4. The Kiro section of the documentation left out things a user hit (the configuration file location, non-interactive trust, IDB, the scale of screenshots, the permissions).
5. The sentence "the real ios-simulator-mcp was not run" is no longer true.

This feature does NOT change the rule that names a coordinate scale problem.

## Glossary

- **Pair**: one mismatch, an agent click and the human click that most likely corrected it.
- **Ratio of a pair**: `ratio_x = agent_x / human_x` and `ratio_y = agent_y / human_y`, in device points.
- **Window**: the longest gap between an agent click and a human click for them to be paired. A gap strictly smaller than the window pairs.
- **Recorder**: the command `poltergeist-kiro-hook`.
- **Agent example**: `integrations/kiro/agents/simdriver.json`, an agent configuration file used with `--agent simdriver`.
- **Demo**: `demo/index.html`, with its check `demo/check_port.py`.

## Requirements

### Requirement 1: The ratio of a pair

**User Story:** As an agent with a single human correction, I want the ratio of that pair, so that I do not compute it by hand.

#### Acceptance Criteria

1. EACH mismatch SHALL have `ratio_x` and `ratio_y`, equal to the normalized agent coordinate divided by the normalized human coordinate (device points).
2. WHEN the absolute value of a human coordinate is below 1.0, THE matching ratio SHALL be `null`. This is the threshold the scale rule uses to skip a sample.
3. THE HTTP route `GET /human-actions` and the MCP tool `get_human_actions` SHALL return the same object with the new fields.
4. THE existing way of building a mismatch with its five fields SHALL keep working: the new fields have defaults (`null`).
5. THE rule that names a coordinate scale problem SHALL NOT change.

### Requirement 2: The ratio in the sentence

**User Story:** As a user reading the activity, I want the ratio in the sentence, so that the model sees it where it reads the mismatch.

#### Acceptance Criteria

1. `describe_mismatch` SHALL add, right after the offset, `, ratio x1.50 / y1.50 for this pair alone`, with two decimals.
2. WHEN one ratio is unknown, THE sentence SHALL use a short form (`x?`, `y?`) and SHALL NOT contain the words `None` or `nan`.
3. WHEN both ratios are unknown, THE sentence SHALL add nothing.
4. A payload without the new keys SHALL be described as before.
5. THE ratio sentence SHALL NOT say that the agent has a scale problem. It is a number for one pair.

### Requirement 3: A configurable pairing window

**User Story:** As a user with a slow tool, I want to set the window, so that late corrections still pair.

#### Acceptance Criteria

1. THE environment variable `POLTERGEIST_MISMATCH_WINDOW_SECONDS` SHALL set the window in seconds. The default is 5.
2. IF the value is not a number, not finite or not above 0, THEN it SHALL be ignored with a warning in the log and 5 SHALL be used.
3. THE pairing rule SHALL be unchanged: a gap strictly smaller than the window pairs.
4. `detection.MISMATCH_WINDOW_SECONDS` SHALL stay a module constant that `demo/check_port.py` can patch.

### Requirement 4: The recorder takes the address

**User Story:** As a user whose Kiro cannot see my virtual environment, I want to give the recorder its address and path, so that the hook works.

#### Acceptance Criteria

1. `poltergeist-kiro-hook` SHALL accept `--url ADDRESS` and `--url=ADDRESS`.
2. THE order of precedence SHALL be `--url`, then `POLTERGEIST_URL`, then `http://127.0.0.1:8000`.
3. ANY other argument, and `--url` without a value, SHALL be ignored. THE recorder SHALL still exit with code 0 and print nothing.
4. `integrations/kiro/hooks/poltergeist.json` SHALL show the command as `/ABSOLUTE/PATH/TO/poltergeist-kiro-hook --url http://127.0.0.1:8000`.
5. `integrations/kiro/agents/simdriver.json` SHALL hold the agent configuration (`name` `simdriver`, `tools` and `allowedTools` `["@ios-simulator", "@poltergeist"]`, `includeMcpJson` true, `resources` `["file://.kiro/steering/**/*.md"]`).

### Requirement 5: The demo follows

**User Story:** As a viewer of the demo, I want it to match the server, so that the page tells the truth.

#### Acceptance Criteria

1. THE core of `demo/index.html` SHALL produce the same ratio and the same sentence as Python for any pair.
2. THE JSON shown on the page SHALL have `ratio_x` and `ratio_y`.
3. `demo/check_port.py` SHALL compare the ratios and the sentences.

### Requirement 6: Documentation

**User Story:** As a user, I want the documentation to say what I will hit.

#### Acceptance Criteria

1. `README.md` and `docs/usage.md` SHALL describe the ratio fields and the sentence, the environment variable (in the table of environment variables) and the `--url` argument.
2. THEY SHALL say that the Kiro MCP configuration file is `.kiro/settings/mcp.json`.
3. THEY SHALL say that `--trust-tools=@ios-simulator/ui_tap` and `--trust-tools=@ios-simulator,@poltergeist` do not let MCP tools run with `--no-interactive` (Kiro says "tool permission approval is not supported in non-interactive mode"), and that an agent configuration file used with `--agent` works. THEY SHALL NOT recommend `--trust-all-tools`, and SHALL say it lets the model run any command without asking.
4. THEY SHALL tell the user to replace the placeholder path in the hook file with the output of `which poltergeist-kiro-hook` from the virtual environment.
5. THEY SHALL say that `ios-simulator-mcp` needs IDB; that on macOS Tahoe Homebrew asks for the Command Line Tools first; that the IDB release package also works with `IOS_SIMULATOR_MCP_IDB_PATH` pointing at the `idb` client; and that "Failed to connect to companion" is fixed by `idb connect <udid>`.
6. THEY SHALL say that `ios-simulator-mcp` scales screenshots (`ui_view`) to device points, so the "pixels read as points" mistake is unusual with it, and that the coordinate scale problem shows up mostly with tools or flows whose screenshots are in pixels.
7. THEY SHALL say what was checked: the real `ios-simulator-mcp` 2.2.1 with IDB 1.7.8 was run and its taps worked; the wrong-scale case was reproduced only with a stand-in tool whose screenshots are 1.5 times the device points; the Kiro IDE has not been used, only `kiro-cli`. THE old sentence "the real ios-simulator-mcp was not run" SHALL be removed.
8. THEY SHALL say plainly that the observer needs the Accessibility and Input Monitoring permissions, which the user must grant in System Settings.

### Requirement 7: Tests and scope

**User Story:** As a maintainer, I want tests, and no change to what works.

#### Acceptance Criteria

1. NEW tests SHALL cover the ratio (values, the 1.0 threshold, defaults, route and tool), the sentence, the window variable and the recorder's `--url`.
2. `tests/test_kiro_hook.py` SHALL be updated where the example hook file changed.
3. NO other existing test SHALL be edited. IF one contradicts the new behaviour, THEN the report says so and work stops.
4. NOTHING that works today SHALL change other than what Requirements 1 to 6 ask.
