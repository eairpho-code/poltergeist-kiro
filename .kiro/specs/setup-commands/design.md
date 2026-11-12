# Design Document

## Overview

This design adds one module, `poltergeist/cli.py`, one console script `poltergeist`, a package-data folder `poltergeist/kiro_files/`, tests and documentation. It changes no existing module. The CLI uses the standard library only (`argparse`, `json`, `os`, `shutil`, `subprocess`, `sys`, `urllib.request`, `importlib.resources`).

```
 poltergeist init kiro ──▶ plan(files) ──▶ apply (or print "would ...") ──▶ one line per file ──▶ next steps
        │                      ▲
        │                      └── package data: poltergeist/kiro_files/  (same bytes as integrations/kiro/)
        └── writes only inside DIR/.kiro/

 poltergeist doctor ──▶ 9 checks in a fixed order ──▶ "[ok|warn|fail] name: detail" ──▶ "N ok, N warn, N fail"
```

## Package data

`poltergeist/kiro_files/` holds copies of `hooks/poltergeist.json`, `steering/poltergeist.md` and `agents/simdriver.json` from `integrations/kiro/`. `pyproject.toml` lists them as package data so `pip install .` installs them next to the code. `integrations/kiro/` stays as the readable copy. A test compares the two byte for byte, so they cannot drift apart. The CLI reads them with `importlib.resources`, never from the repository.

## The CLI: poltergeist/cli.py

- `main(argv=None) -> int` builds an `argparse` parser with sub-commands `init` (target `kiro`) and `doctor`. `argparse` exits with 2 on an unknown command or a missing argument; `main` returns that code instead of letting `SystemExit` escape when called from Python. `--help` returns 0.
- `if __name__ == "__main__": sys.exit(main())` makes `python -m poltergeist.cli` work.

## init kiro

1. Validate: the folder must exist and the address must start with `http://` or `https://`; otherwise print a message to standard error and return 2 before anything is written.
2. Build a plan of four items, each `(relative path, wanted bytes or a merge)`.
3. For each file decide a status:
   - missing: `created`;
   - equal to the wanted content: `unchanged`;
   - different: `skipped` with a reason, or with `--force` `updated`.
4. With `--dry-run` the same decisions are made but nothing is written and the line reads `would create`, `would update`, `would skip` or `unchanged`. Every dry-run line contains `would`; an unchanged file reads `would leave unchanged`.
5. Parent folders are made only under `DIR/.kiro/`. The path of each file is checked to be inside `DIR/.kiro/` before writing.
6. The exit code is 1 when any status was `skipped`, or when the hook file could not be written for lack of a `poltergeist-kiro-hook`; otherwise 0.

### The hook file

The package-data hook file is parsed, the command of the first hook is replaced and the result is written with `json.dumps(indent=2)` plus a newline. The command is `PATH --url ADDRESS`. The path is the file `poltergeist-kiro-hook` in `os.path.dirname(sys.executable)`; if it is not an executable file, `shutil.which("poltergeist-kiro-hook")`; if there is none, the line is `skipped` with the reason, nothing is written for that file and the exit code is 1. The path is made absolute; when it contains whitespace the whole path is wrapped in double quotes. The command is compared with the existing file after this substitution, so a second run is `unchanged`.

### The MCP file

- Missing: the file is created with the two entries.
- Present: it is parsed. Invalid JSON, or a top level that is not an object, is `skipped` and never changed, even with `--force`. A `mcpServers` value that is not an object is treated the same way.
- Entries are added under `mcpServers`. Each of `poltergeist` and `ios-simulator` is added only when absent. An entry that equals the wanted value is `unchanged`. A different entry is a conflict: `skipped` and left as it is; with `--force` it is replaced. Every other key and server is kept in its original order.
- `poltergeist` is `{"url": "ADDRESS/mcp"}` where a trailing slash of ADDRESS is removed first. `ios-simulator` is `{"command": "npx", "args": ["-y", "ios-simulator-mcp"]}`.
- When one entry is a conflict and the other is missing, the missing one is still added and the line is `skipped` for the conflict.

### Output

One line per file, `STATUS PATH`, with ` (reason)` after `skipped`. After the lines come the next steps: start the server (`POLTERGEIST_TRANSPORT=streamable-http poltergeist-server`), build and start the observer, grant the Accessibility and Input Monitoring permissions in System Settings (this command does not and cannot), and run `poltergeist doctor`.

## doctor

`doctor` runs nine checks in the fixed order `server`, `hooks`, `steering`, `agent`, `mcp`, `observer`, `simulator`, `idb`, `kiro`. Each check is a function returning `(level, name, detail)`; `level` is `ok`, `warn` or `fail`. A check that raises is caught and reported as its own failing level with the error text, so `doctor` never prints a traceback. Nothing is written.

- `server`: `urllib.request.urlopen(ADDRESS + "/human-actions", timeout=5)`; the body must be a JSON object with `human_actions`. Level `fail`.
- `hooks`: file exists, valid JSON, `hooks` has a `PreToolUse` and a `PostToolUse` hook; the command is split with `shlex.split`; the first token is absolute, a file and executable. The `--url` token is compared with ADDRESS and a difference is a warning in the detail (the level stays `ok`). Level `fail`.
- `steering`: file exists. Level `warn`.
- `agent`: file exists and is valid JSON. Level `warn`.
- `mcp`: valid JSON; `mcpServers.poltergeist.url == ADDRESS/mcp`; `mcpServers["ios-simulator"]` exists. Level `fail`.
- `observer`, `simulator`, `idb`, `kiro`: external commands through one helper `run_tool(args)` that uses `subprocess.run` with `timeout=5`, `capture_output=True` and `text=True`, and returns `None` on `OSError` or `TimeoutExpired`. They are looked up on the PATH by name. A `None` result or a failing exit status is a `warn` with a fix.
  - `observer`: `pgrep -x poltergeist-observer` exits 0.
  - `simulator`: `xcrun simctl list devices booted` prints a line with `Booted`.
  - `idb`: the client is `IOS_SIMULATOR_MCP_IDB_PATH` if set, else `idb` on the PATH; `idb list-targets` must print something. The fix mentions `idb connect <udid>`.
  - `kiro`: `kiro-cli --version` exits 0.

The last lines are `N ok, N warn, N fail` and a note that the Accessibility and Input Monitoring permissions cannot be checked from here. The exit code is 1 when any level is `fail`, otherwise 0.

## Testing

- Unit tests call `main([...])` with temporary folders: first run, second run (`unchanged`), conflicts, `--force`, invalid JSON, `--dry-run` writes nothing, bad `--dir` and `--url` exit 2 and write nothing, a path with whitespace is quoted, and nothing is written outside `.kiro/`.
- A test checks `poltergeist/kiro_files/` equals `integrations/kiro/`.
- `doctor` tests use a local stub HTTP server and a temporary PATH with fake `pgrep`, `xcrun`, `idb` and `kiro-cli` scripts, including a missing command and a command that hangs.
