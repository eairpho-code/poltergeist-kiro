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
import sys
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
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
