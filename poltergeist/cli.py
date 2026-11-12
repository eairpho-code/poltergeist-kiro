"""The ``poltergeist`` command: set Poltergeist up in a Kiro project.

``poltergeist init kiro`` writes the Kiro hooks, steering, agent file and MCP
configuration into ``DIR/.kiro/``. The content comes from package data inside
the installed package (``poltergeist/kiro_files/``), so it works from a clean
``pip install``. Standard library only.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import urllib.request
from importlib import resources
from typing import Callable, List, Optional, Tuple

DEFAULT_URL = "http://127.0.0.1:8000"
HOOK_COMMAND_NAME = "poltergeist-kiro-hook"

CREATED = "created"
UNCHANGED = "unchanged"
UPDATED = "updated"
SKIPPED = "skipped"

# (status, reason, bytes to write or None)
Decision = Tuple[str, str, Optional[bytes]]


def _package_file(*parts: str) -> bytes:
    node = resources.files("poltergeist").joinpath("kiro_files", *parts)
    return node.read_bytes()


def _read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def find_hook_executable() -> Optional[str]:
    """Absolute path of ``poltergeist-kiro-hook`` that belongs to this Python."""
    candidate = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), HOOK_COMMAND_NAME)
    if _executable(candidate):
        return os.path.abspath(candidate)
    found = shutil.which(HOOK_COMMAND_NAME)
    if found:
        return os.path.abspath(found)
    return None


def hook_command(executable: str, url: str) -> str:
    """``PATH --url ADDRESS``; a path with whitespace is wrapped in double quotes."""
    path = executable
    if any(ch.isspace() for ch in path):
        path = '"' + path + '"'
    return f"{path} --url {url}"


def _plain_decision(existing: Optional[bytes], wanted: bytes, force: bool) -> Decision:
    if existing is None:
        return CREATED, "", wanted
    if existing == wanted:
        return UNCHANGED, "", None
    if force:
        return UPDATED, "", wanted
    return SKIPPED, "exists with different content; use --force to overwrite", None


def _hook_decision(existing: Optional[bytes], url: str, force: bool) -> Decision:
    executable = find_hook_executable()
    if executable is None:
        return SKIPPED, f"no {HOOK_COMMAND_NAME} found next to {sys.executable} or on the PATH", None
    data = json.loads(_package_file("hooks", "poltergeist.json"))
    data["hooks"][0]["action"]["command"] = hook_command(executable, url)
    wanted = (json.dumps(data, indent=2) + "\n").encode("utf-8")
    if existing is not None:
        try:
            if json.loads(existing) == data:
                return UNCHANGED, "", None
        except ValueError:
            pass
    return _plain_decision(existing, wanted, force)


def wanted_mcp_entries(url: str) -> dict:
    return {
        "poltergeist": {"url": url.rstrip("/") + "/mcp"},
        "ios-simulator": {"command": "npx", "args": ["-y", "ios-simulator-mcp"]},
    }


def _mcp_decision(existing: Optional[bytes], url: str, force: bool) -> Decision:
    entries = wanted_mcp_entries(url)
    if existing is None:
        wanted = (json.dumps({"mcpServers": entries}, indent=2) + "\n").encode("utf-8")
        return CREATED, "", wanted
    try:
        data = json.loads(existing.decode("utf-8"))
    except ValueError:
        return SKIPPED, "not valid JSON; left as it is", None
    if not isinstance(data, dict):
        return SKIPPED, "top level is not a JSON object; left as it is", None
    servers = data.get("mcpServers")
    if "mcpServers" in data and not isinstance(servers, dict):
        return SKIPPED, "mcpServers is not a JSON object; left as it is", None
    if servers is None:
        servers = {}
    changed = False
    conflicts: List[str] = []
    for name, value in entries.items():
        if name not in servers:
            servers[name] = value
            changed = True
        elif servers[name] == value:
            continue
        elif force:
            servers[name] = value
            changed = True
        else:
            conflicts.append(name)
    data["mcpServers"] = servers
    wanted = (json.dumps(data, indent=2) + "\n").encode("utf-8") if changed else None
    if conflicts:
        reason = "conflict: " + ", ".join(conflicts) + " exists with different content; use --force to replace"
        return SKIPPED, reason, wanted
    if changed:
        return UPDATED, "", wanted
    return UNCHANGED, "", None


def _inside(root: str, path: str) -> bool:
    root_real = os.path.realpath(root)
    path_real = os.path.realpath(path)
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def _write(kiro_dir: str, path: str, content: bytes) -> None:
    if not _inside(kiro_dir, path):
        raise OSError(f"refusing to write outside {kiro_dir}: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)


def _line(status: str, path: str, reason: str, dry_run: bool) -> str:
    if not dry_run:
        text = f"{status} {path}"
        return f"{text} ({reason})" if status == SKIPPED and reason else text
    if status == UNCHANGED:
        return f"would leave unchanged {path}"
    verb = {CREATED: "would create", UPDATED: "would update", SKIPPED: "would skip"}[status]
    text = f"{verb} {path}"
    return f"{text} ({reason})" if status == SKIPPED and reason else text


NEXT_STEPS = """
Next steps:
  1. Start the server:
       POLTERGEIST_TRANSPORT=streamable-http poltergeist-server
  2. Build and start the macOS observer (see the README, "The macOS observer").
  3. Grant the Accessibility and Input Monitoring permissions to the observer in
     System Settings > Privacy & Security. Nothing in this command grants them;
     only you can.
  4. Check the setup:
       poltergeist doctor"""


def run_init(directory: str, url: str, force: bool, dry_run: bool) -> int:
    if not os.path.isdir(directory):
        print(f"poltergeist: --dir {directory!r} is not an existing folder", file=sys.stderr)
        return 2
    if not (url.startswith("http://") or url.startswith("https://")):
        print(f"poltergeist: --url {url!r} must start with http:// or https://", file=sys.stderr)
        return 2

    kiro_dir = os.path.join(directory, ".kiro")
    plan: List[Tuple[str, Callable[[Optional[bytes]], Decision]]] = [
        (os.path.join("hooks", "poltergeist.json"), lambda e: _hook_decision(e, url, force)),
        (
            os.path.join("steering", "poltergeist.md"),
            lambda e: _plain_decision(e, _package_file("steering", "poltergeist.md"), force),
        ),
        (
            os.path.join("agents", "simdriver.json"),
            lambda e: _plain_decision(e, _package_file("agents", "simdriver.json"), force),
        ),
        (os.path.join("settings", "mcp.json"), lambda e: _mcp_decision(e, url, force)),
    ]

    exit_code = 0
    for relative, decide in plan:
        path = os.path.join(kiro_dir, relative)
        try:
            status, reason, content = decide(_read_bytes(path))
            if content is not None and not dry_run:
                _write(kiro_dir, path, content)
        except OSError as error:
            status, reason = SKIPPED, f"could not write: {error}"
        print(_line(status, path, reason, dry_run))
        if status == SKIPPED:
            exit_code = 1
    print(NEXT_STEPS)
    return exit_code


# --- doctor ---------------------------------------------------------------------------

COMMAND_TIMEOUT = 5.0
HTTP_TIMEOUT = 5.0
START_SERVER = "start it with: POLTERGEIST_TRANSPORT=streamable-http poltergeist-server"

OK, WARN, FAIL = "ok", "warn", "fail"
Check = Tuple[str, str]  # (status, detail)


def run_tool(argv: List[str]) -> Optional[Tuple[int, str]]:
    """Run an external command found on the PATH. None when missing, hung or unrunnable."""
    exe = shutil.which(argv[0]) if os.sep not in argv[0] else argv[0]
    if exe is None:
        return None
    try:
        proc = subprocess.Popen(
            [exe, *argv[1:]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    try:
        out, _ = proc.communicate(timeout=COMMAND_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        return None
    return proc.returncode, out.decode("utf-8", errors="replace")


def _load_json_file(path: str):
    """(data, error) for a JSON file; error is a short text or None."""
    raw = _read_bytes(path)
    if raw is None:
        return None, "missing"
    try:
        return json.loads(raw.decode("utf-8")), None
    except ValueError:
        return None, "not valid JSON"


def check_server(url: str) -> Check:
    target = url.rstrip("/") + "/human-actions"
    fix = f"no Poltergeist server at {url}; {START_SERVER}"
    try:
        with urllib.request.urlopen(target, timeout=HTTP_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:  # network, HTTP or JSON problems all mean "not usable"
        return FAIL, f"{fix} ({type(error).__name__})"
    if isinstance(data, dict) and "human_actions" in data:
        return OK, f"{target} answers"
    return FAIL, f"{target} did not answer with human_actions; {START_SERVER}"


def check_hooks(kiro_dir: str, url: str) -> Check:
    path = os.path.join(kiro_dir, "hooks", "poltergeist.json")
    fix = "run: poltergeist init kiro" 
    data, error = _load_json_file(path)
    if error:
        return FAIL, f"{path} is {error}; {fix} (add --force to rewrite it)" if error != "missing" else f"{path} is missing; {fix}"
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, list) or len(hooks) < 2 or not all(isinstance(h, dict) for h in hooks):
        return FAIL, f"{path} does not hold the two hooks; {fix} --force"
    pre = next((h for h in hooks if h.get("trigger") == "PreToolUse"), None)
    post = next((h for h in hooks if h.get("trigger") == "PostToolUse"), None)
    if pre is None or post is None:
        return FAIL, f"{path} needs a PreToolUse and a PostToolUse hook; {fix} --force"
    action = pre.get("action")
    command = action.get("command") if isinstance(action, dict) else None
    if not isinstance(command, str) or not command.strip():
        return FAIL, f"the PreToolUse hook has no command; {fix} --force"
    command = command.strip()
    if command.startswith('"'):
        end = command.find('"', 1)
        first = command[1:end] if end > 0 else command[1:]
        rest = command[end + 1:] if end > 0 else ""
    else:
        first, _, rest = command.partition(" ")
    if not os.path.isabs(first):
        return FAIL, f"the hook command {first!r} is not an absolute path; {fix} --force"
    if not _executable(first):
        return FAIL, f"the hook command {first} is not an executable file; {fix} --force with the right Python active"
    detail = f"{path} runs {first}"
    tokens = rest.split()
    hook_url = tokens[tokens.index("--url") + 1] if "--url" in tokens[:-1] else None
    if hook_url is None:
        for token in tokens:
            if token.startswith("--url="):
                hook_url = token[len("--url="):]
    if hook_url is not None and hook_url.rstrip("/") != url.rstrip("/"):
        detail += f" (warning: its --url is {hook_url}, not {url}; run: poltergeist init kiro --url {url} --force)"
    return OK, detail


def check_exists(kiro_dir: str, relative: str, must_be_json: bool) -> Check:
    path = os.path.join(kiro_dir, relative)
    if must_be_json:
        _, error = _load_json_file(path)
        if error == "missing":
            return WARN, f"{path} is missing; run: poltergeist init kiro"
        if error:
            return WARN, f"{path} is {error}; fix it or run: poltergeist init kiro --force"
        return OK, path
    if not os.path.isfile(path):
        return WARN, f"{path} is missing; run: poltergeist init kiro"
    return OK, path


def check_mcp(kiro_dir: str, url: str) -> Check:
    path = os.path.join(kiro_dir, "settings", "mcp.json")
    data, error = _load_json_file(path)
    if error == "missing":
        return FAIL, f"{path} is missing; run: poltergeist init kiro --url {url}"
    if error:
        return FAIL, f"{path} is {error}; fix it by hand, then run: poltergeist init kiro --url {url}"
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return FAIL, f"{path} has no mcpServers object; run: poltergeist init kiro --url {url}"
    wanted = url.rstrip("/") + "/mcp"
    entry = servers.get("poltergeist")
    if not isinstance(entry, dict) or entry.get("url") != wanted:
        found = entry.get("url") if isinstance(entry, dict) else None
        return FAIL, f"poltergeist in {path} should have the url {wanted} (found {found!r}); run: poltergeist init kiro --url {url} --force"
    if "ios-simulator" not in servers:
        return FAIL, f"ios-simulator is missing from {path}; run: poltergeist init kiro --url {url}"
    return OK, f"{path} has poltergeist at {wanted} and ios-simulator"


def check_observer() -> Check:
    result = run_tool(["pgrep", "-x", "poltergeist-observer"])
    if result is not None and result[0] == 0:
        return OK, "poltergeist-observer is running"
    return WARN, "poltergeist-observer is not running; build it (cd observer && swift build -c release) and start it"


def check_simulator() -> Check:
    result = run_tool(["xcrun", "simctl", "list", "devices", "booted"])
    if result is not None and result[0] == 0 and any("Booted" in line for line in result[1].splitlines()):
        return OK, "a simulator is booted"
    return WARN, "no booted simulator found; boot one in Xcode or with: xcrun simctl boot <udid>"


def check_idb() -> Check:
    fix = "install IDB, set IOS_SIMULATOR_MCP_IDB_PATH to the idb client, and run: idb connect <udid>"
    configured = os.environ.get("IOS_SIMULATOR_MCP_IDB_PATH")
    idb = configured if configured else shutil.which("idb")
    if not idb or not _executable(idb) and not shutil.which(idb):
        return WARN, f"the idb client was not found; {fix}"
    result = run_tool([idb, "list-targets"])
    if result is not None and result[0] == 0 and result[1].strip():
        return OK, f"{idb} lists a target"
    return WARN, f"{idb} lists no targets; run: idb connect <udid>"


def check_kiro() -> Check:
    result = run_tool(["kiro-cli", "--version"])
    if result is not None and result[0] == 0:
        return OK, result[1].strip() or "kiro-cli runs"
    return WARN, "kiro-cli was not found or did not run; install Kiro CLI and put it on the PATH"


def run_doctor(directory: str, url: str) -> int:
    kiro_dir = os.path.join(directory, ".kiro")
    checks: List[Tuple[str, Callable[[], Check]]] = [
        ("server", lambda: check_server(url)),
        ("hooks", lambda: check_hooks(kiro_dir, url)),
        ("steering", lambda: check_exists(kiro_dir, os.path.join("steering", "poltergeist.md"), False)),
        ("agent", lambda: check_exists(kiro_dir, os.path.join("agents", "simdriver.json"), True)),
        ("mcp", lambda: check_mcp(kiro_dir, url)),
        ("observer", check_observer),
        ("simulator", check_simulator),
        ("idb", check_idb),
        ("kiro", check_kiro),
    ]
    counts = {OK: 0, WARN: 0, FAIL: 0}
    for name, check in checks:
        try:
            status, detail = check()
        except Exception as error:  # a check must never crash doctor
            status, detail = WARN, f"could not be checked ({type(error).__name__}: {error})"
        counts[status] += 1
        print(f"[{status}] {name}: {detail}")
    print(f"{counts[OK]} ok, {counts[WARN]} warn, {counts[FAIL]} fail")
    print(
        "Note: the Accessibility and Input Monitoring permissions cannot be checked from here; "
        "check them in System Settings > Privacy & Security."
    )
    return 1 if counts[FAIL] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poltergeist", description="Set up Poltergeist in a Kiro project."
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    init = commands.add_parser("init", help="set up a project")
    targets = init.add_subparsers(dest="target", required=True, metavar="TARGET")
    kiro = targets.add_parser(
        "kiro",
        help="write the Kiro hooks, steering, agent file and MCP configuration",
        description="Write the Poltergeist files into DIR/.kiro/. Exit code 0 when every "
        "file is created, unchanged or updated; 1 when anything was skipped; 2 for a bad argument.",
    )
    kiro.add_argument("--dir", default=".", help="the project folder (default: the current folder)")
    kiro.add_argument("--url", default=DEFAULT_URL, help=f"the server address (default: {DEFAULT_URL})")
    kiro.add_argument("--force", action="store_true", help="overwrite files that differ")
    kiro.add_argument("--dry-run", action="store_true", help="write nothing; print what would happen")
    doctor = commands.add_parser(
        "doctor",
        help="check the project and the machine",
        description="Check a Kiro project and the machine; change nothing. Exit code 1 when any "
        "check fails, otherwise 0.",
    )
    doctor.add_argument("--dir", default=".", help="the project folder (default: the current folder)")
    doctor.add_argument("--url", default=DEFAULT_URL, help=f"the server address (default: {DEFAULT_URL})")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        code = exit_.code
        return code if isinstance(code, int) else (0 if code is None else 2)
    if args.command == "init" and args.target == "kiro":
        return run_init(args.dir, args.url, args.force, args.dry_run)
    if args.command == "doctor":
        return run_doctor(args.dir, args.url)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
