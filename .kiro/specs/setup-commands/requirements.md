# Requirements Document

## Introduction

Setting Poltergeist up in Kiro takes several hand steps: copy three files, merge `mcp.json`, put the right path in the hook, write an agent file. When one is wrong nothing says which. This feature adds a console script `poltergeist` with two commands:

- `poltergeist init kiro` sets up a Kiro project in one step.
- `poltergeist doctor` checks the project and the machine and says how to fix what is wrong.

What a real run showed, and what this feature relies on:

- Kiro runs a hook command without the virtual environment on its PATH, so the hook command is written with an absolute path and its server address as an argument.
- The MCP configuration file of a Kiro project is `.kiro/settings/mcp.json`. Hooks go in `.kiro/hooks/`, steering in `.kiro/steering/`, agent files in `.kiro/agents/`.
- `kiro-cli chat --v3 --no-interactive` needs the agent file `simdriver` to let MCP tools run.
- The macOS observer needs the Accessibility and Input Monitoring permissions. Only the user can grant them; no command can or should.
- `ios-simulator-mcp` needs IDB and a running IDB companion.
- The example files in `integrations/kiro/` are not part of the installed package today, so the commands must carry their content as package data and work from an installed package in a clean virtual environment.

## Glossary

- **CLI**: the console script `poltergeist`, the module `poltergeist/cli.py`. Standard library only.
- **Project**: the folder given by `--dir`; its Kiro files live in `DIR/.kiro/`.
- **Address**: the server base URL given by `--url`, default `http://127.0.0.1:8000`.
- **Hook command**: the command of the `PreToolUse` hook, `ABSOLUTE_PATH --url ADDRESS`.
- **Package data**: the copies of the example files stored inside the installed `poltergeist` package.
- **Example files**: the readable copies in `integrations/kiro/`.
- **Poltergeist entries**: the two `mcp.json` servers `poltergeist` and `ios-simulator`.
- **Status**: one of `created`, `unchanged`, `updated`, `skipped`.

## Requirements

### Requirement 1: The console script

**User Story:** As a user, I want one command with clear exit codes, so that I can script the setup.

#### Acceptance Criteria

1. THE CLI SHALL be defined as the console script `poltergeist` in `pyproject.toml`, with `main(argv=None) -> int`, and `python -m poltergeist.cli` SHALL work.
2. `poltergeist --help` SHALL exit 0.
3. An unknown command, or a missing argument (such as `poltergeist init` without a target), SHALL exit 2.
4. THE CLI SHALL use the standard library only and SHALL never print a traceback for an expected failure.

### Requirement 2: Validate the arguments before writing

**User Story:** As a user, I want a mistake in an argument to change nothing.

#### Acceptance Criteria

1. `--dir` SHALL default to the current folder. IF the folder does not exist, THEN `init kiro` SHALL exit 2 and write nothing.
2. `--url` SHALL default to `http://127.0.0.1:8000`. IF it does not start with `http://` or `https://`, THEN `init kiro` SHALL exit 2 and write nothing.
3. `init kiro` SHALL write only inside `DIR/.kiro/`, never elsewhere in the project, never outside it and never in the home folder.

### Requirement 3: The hook file

**User Story:** As a user, I want a hook command that works when Kiro runs it without my virtual environment.

#### Acceptance Criteria

1. `init kiro` SHALL write `.kiro/hooks/poltergeist.json` with the two hooks of `integrations/kiro/hooks/poltergeist.json`.
2. THE command of the first hook SHALL be the absolute path of `poltergeist-kiro-hook` that belongs to the Python that runs the CLI (the file next to `sys.executable`; otherwise the result of `shutil.which`), followed by `--url ADDRESS`.
3. A path that contains whitespace SHALL be wrapped in double quotes.
4. IF no such file exists, THEN `init kiro` SHALL say so, SHALL not write the hook file and SHALL exit 1; the other files SHALL still be written.

### Requirement 4: Steering and agent files from package data

**User Story:** As a user who installed with `pip install .`, I want the files even though the repository is not next to the code.

#### Acceptance Criteria

1. `init kiro` SHALL write `.kiro/steering/poltergeist.md` and `.kiro/agents/simdriver.json` with the content of the files in `integrations/kiro/`.
2. THE content SHALL come from package data inside the installed package, with `integrations/kiro/` kept as the readable copy.
3. A test SHALL check that the package data and the example files are identical, so they cannot drift apart.

### Requirement 5: Merge the MCP configuration

**User Story:** As a user with other MCP servers, I want my configuration kept.

#### Acceptance Criteria

1. `init kiro` SHALL merge into `.kiro/settings/mcp.json` and SHALL never replace it: every other key and every other server stays.
2. IT SHALL add `poltergeist` as `{"url": "ADDRESS/mcp"}` (no double slash when ADDRESS ends with a slash) and `ios-simulator` as `{"command": "npx", "args": ["-y", "ios-simulator-mcp"]}`, each only when it is absent.
3. WHEN one of the two exists with different content, THE CLI SHALL leave it unchanged and report a conflict (`skipped`).
4. WITH `--force`, only the two Poltergeist entries SHALL be replaced.
5. A file that is not valid JSON, or whose top level is not an object, SHALL be `skipped` and never changed, even with `--force`.

### Requirement 6: Report, re-run, force and dry run

**User Story:** As a user, I want to see what happened to each file and to be able to run the command again safely.

#### Acceptance Criteria

1. `init kiro` SHALL print one line per file: the status followed by the path, and the reason after `skipped`.
2. A file that exists with different content SHALL be `skipped` and left as it is, unless `--force` is given; with `--force` it SHALL be overwritten and reported `updated`.
3. Running it twice SHALL change nothing the second time: every file is `unchanged` and nothing is `created`.
4. WITH `--dry-run`, nothing SHALL be written, and each line SHALL say what would happen and contain the word `would`.
5. THE exit code SHALL be 0 when every file is `created`, `unchanged` or `updated`, and 1 when anything was `skipped`. Other files SHALL still be written when one is skipped.

### Requirement 7: Next steps

**User Story:** As a user, I want to know what is left to do by hand.

#### Acceptance Criteria

1. AT THE END, `init kiro` SHALL print the next steps: start the server (`POLTERGEIST_TRANSPORT=streamable-http poltergeist-server`), build and start the observer, grant the Accessibility and Input Monitoring permissions in System Settings, and run `poltergeist doctor`.
2. IT SHALL say plainly that nothing in this command grants the permissions.

### Requirement 8: doctor reports

**User Story:** As a user, I want one line per check that says what is wrong and how to fix it.

#### Acceptance Criteria

1. `doctor [--dir DIR] [--url ADDRESS]` SHALL change nothing.
2. IT SHALL print one line per check, in this order, as `[ok] name: detail`, `[warn] name: detail` or `[fail] name: detail`, and a `warn` or `fail` line SHALL say how to fix it.
3. THE names SHALL be, in order: `server`, `hooks`, `steering`, `agent`, `mcp`, `observer`, `simulator`, `idb`, `kiro`.
4. IT SHALL end with the line `N ok, N warn, N fail` and a note that the Accessibility and Input Monitoring permissions cannot be checked from here.
5. THE exit code SHALL be 1 when any check is `fail`, otherwise 0.

### Requirement 9: The checks

**User Story:** As a user, I want each check to test one clear thing.

#### Acceptance Criteria

1. `server` (fail): `GET ADDRESS/human-actions` answers with JSON that has `human_actions`. The fix says to start `POLTERGEIST_TRANSPORT=streamable-http poltergeist-server`.
2. `hooks` (fail): `.kiro/hooks/poltergeist.json` exists, is valid, has the two hooks, and the first token of the `PreToolUse` command is an absolute path to an existing executable file. The detail warns when its `--url` is not ADDRESS.
3. `steering` (warn): `.kiro/steering/poltergeist.md` exists.
4. `agent` (warn): `.kiro/agents/simdriver.json` exists and is valid JSON.
5. `mcp` (fail): `.kiro/settings/mcp.json` is valid JSON, has `poltergeist` with the url `ADDRESS/mcp`, and has `ios-simulator`.
6. `observer` (warn): `pgrep -x poltergeist-observer` exits 0.
7. `simulator` (warn): `xcrun simctl list devices booted` prints a line with `Booted`.
8. `idb` (warn): the `idb` client is found (the path in `IOS_SIMULATOR_MCP_IDB_PATH` if set, otherwise `idb` on the PATH) and `idb list-targets` prints something. The fix mentions `idb connect <udid>`.
9. `kiro` (warn): `kiro-cli --version` exits 0.

### Requirement 10: External commands never break doctor

**User Story:** As a user, I want doctor to finish even when a tool is missing or stuck.

#### Acceptance Criteria

1. External commands SHALL be looked up on the PATH by name, each with a timeout of at most 5 seconds.
2. A command that is missing, fails or hangs SHALL make that check a `warn`; it SHALL never make `doctor` crash or print a traceback.

### Requirement 11: Tests and documentation

**User Story:** As a maintainer, I want the behaviour tested and documented.

#### Acceptance Criteria

1. Tests SHALL cover each requirement above, including a clean-install run of the package data.
2. `README.md` and `docs/usage.md` SHALL describe `poltergeist init kiro` and `poltergeist doctor`, keep the manual steps as the alternative, explain the exit codes, `--dry-run` and `--force`, say that the observer must still be built and started and the permissions granted by the user, and say that `doctor` cannot check the permissions.
3. No existing behaviour SHALL change.
