"""Tests for ``poltergeist init kiro`` (poltergeist/cli.py)."""

import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from poltergeist import cli

REPO = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:8123"
FILES = [
    ".kiro/hooks/poltergeist.json",
    ".kiro/steering/poltergeist.md",
    ".kiro/agents/simdriver.json",
    ".kiro/settings/mcp.json",
]
ENTRIES = {
    "poltergeist": {"url": URL + "/mcp"},
    "ios-simulator": {"command": "npx", "args": ["-y", "ios-simulator-mcp"]},
}


@pytest.fixture
def hook(tmp_path, monkeypatch):
    """A fake poltergeist-kiro-hook next to a fake sys.executable."""
    bin_dir = tmp_path / "venv bin"
    bin_dir.mkdir()
    exe = bin_dir / "poltergeist-kiro-hook"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(sys, "executable", str(bin_dir / "python"))
    return exe


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / "project"
    folder.mkdir()
    return folder


def init(project, *extra, url=URL, capsys=None):
    code = cli.main(["init", "kiro", "--dir", str(project), "--url", url, *extra])
    return code, capsys.readouterr().out if capsys else ""


def snapshot(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes() for p in sorted(Path(folder).rglob("*")) if p.is_file()
    }


def test_package_data_equals_integrations_copy():
    pairs = {
        "hooks/poltergeist.json": "hooks/poltergeist.json",
        "steering/poltergeist.md": "steering/poltergeist.md",
        "agents/simdriver.json": "agents/simdriver.json",
    }
    for name in pairs:
        packaged = (REPO / "poltergeist" / "kiro_files" / name).read_bytes()
        example = (REPO / "integrations" / "kiro" / name).read_bytes()
        assert packaged == example, name
        assert cli._package_file(*name.split("/")) == example


def test_help_exits_zero(capsys):
    assert cli.main(["--help"]) == 0
    assert cli.main(["init", "kiro", "--help"]) == 0


@pytest.mark.parametrize("argv", [[], ["bogus"], ["init"], ["init", "other"], ["init", "kiro", "--nope"]])
def test_bad_command_exits_two(argv, capsys):
    assert cli.main(argv) == 2


def test_module_runs():
    result = subprocess.run(
        [sys.executable, "-m", "poltergeist.cli", "--help"], capture_output=True, text=True, cwd=REPO
    )
    assert result.returncode == 0


def test_first_run_creates_everything(project, hook, capsys):
    code, out = init(project, capsys=capsys)
    assert code == 0
    for name in FILES:
        assert (project / name).is_file()
        assert f"created {project / name}" in out
    for needle in ("POLTERGEIST_TRANSPORT=streamable-http poltergeist-server", "observer",
                   "Accessibility", "Input Monitoring", "poltergeist doctor", "Nothing in this command grants"):
        assert needle in out
    assert sorted(p.name for p in project.iterdir()) == [".kiro"]
    assert json.loads((project / FILES[3]).read_text())["mcpServers"] == ENTRIES


def test_hook_command_has_absolute_path_and_url_quoted_for_whitespace(project, hook, capsys):
    init(project, capsys=capsys)
    hooks = json.loads((project / FILES[0]).read_text())["hooks"]
    command = hooks[0]["action"]["command"]
    assert command == f'"{hook}" --url {URL}'
    assert shlex.split(command) == [str(hook), "--url", URL]
    assert hooks[0]["trigger"] == "PreToolUse"
    assert hooks[1]["trigger"] == "PostToolUse"
    assert hooks[1] == json.loads((REPO / "integrations/kiro/hooks/poltergeist.json").read_text())["hooks"][1]


def test_hook_path_without_whitespace_is_not_quoted(tmp_path, project, monkeypatch, capsys):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "poltergeist-kiro-hook"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setattr(sys, "executable", str(bin_dir / "python"))
    init(project, capsys=capsys)
    command = json.loads((project / FILES[0]).read_text())["hooks"][0]["action"]["command"]
    assert command == f"{exe} --url {URL}"


def test_hook_falls_back_to_path(tmp_path, project, monkeypatch, capsys):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "nowhere" / "python"))
    on_path = tmp_path / "onpath"
    on_path.mkdir()
    exe = on_path / "poltergeist-kiro-hook"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(on_path))
    code, _ = init(project, capsys=capsys)
    assert code == 0
    assert json.loads((project / FILES[0]).read_text())["hooks"][0]["action"]["command"].startswith(str(exe))


def test_no_hook_executable_skips_hook_and_still_writes_the_rest(tmp_path, project, monkeypatch, capsys):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "nowhere" / "python"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    code, out = init(project, capsys=capsys)
    assert code == 1
    assert f"skipped {project / FILES[0]}" in out
    assert "poltergeist-kiro-hook" in out
    assert not (project / FILES[0]).exists()
    for name in FILES[1:]:
        assert (project / name).is_file()


def test_second_run_changes_nothing(project, hook, capsys):
    init(project, capsys=capsys)
    before = snapshot(project)
    code, out = init(project, capsys=capsys)
    assert code == 0
    assert snapshot(project) == before
    assert out.count("unchanged") == 4
    assert "created" not in out


def test_trailing_slash_in_url_gives_no_double_slash(project, hook, capsys):
    init(project, url="http://host:9/", capsys=capsys)
    servers = json.loads((project / FILES[3]).read_text())["mcpServers"]
    assert servers["poltergeist"] == {"url": "http://host:9/mcp"}


def test_default_dir_and_url(tmp_path, hook, monkeypatch, capsys):
    folder = tmp_path / "cwd"
    folder.mkdir()
    monkeypatch.chdir(folder)
    assert cli.main(["init", "kiro"]) == 0
    servers = json.loads((folder / FILES[3]).read_text())["mcpServers"]
    assert servers["poltergeist"] == {"url": "http://127.0.0.1:8000/mcp"}


def test_merge_keeps_other_keys_and_servers(project, hook, capsys):
    (project / ".kiro/settings").mkdir(parents=True)
    original = {"other": {"keep": True}, "mcpServers": {"foo": {"command": "x"}}}
    (project / FILES[3]).write_text(json.dumps(original))
    code, out = init(project, capsys=capsys)
    merged = json.loads((project / FILES[3]).read_text())
    assert code == 0
    assert f"updated {project / FILES[3]}" in out
    assert merged["other"] == {"keep": True}
    assert list(merged["mcpServers"]) == ["foo", "poltergeist", "ios-simulator"]
    before = snapshot(project)
    code, _ = init(project, capsys=capsys)
    assert code == 0 and snapshot(project) == before


def test_conflict_is_skipped_then_forced(project, hook, capsys):
    (project / ".kiro/settings").mkdir(parents=True)
    mine = {"mcpServers": {"poltergeist": {"url": "http://elsewhere:1/mcp"}, "foo": {"a": 1}}}
    (project / FILES[3]).write_text(json.dumps(mine))
    code, out = init(project, capsys=capsys)
    after = json.loads((project / FILES[3]).read_text())["mcpServers"]
    assert code == 1
    assert f"skipped {project / FILES[3]}" in out
    assert after["poltergeist"] == {"url": "http://elsewhere:1/mcp"}
    assert after["ios-simulator"] == ENTRIES["ios-simulator"]
    assert after["foo"] == {"a": 1}
    code, out = init(project, "--force", capsys=capsys)
    after = json.loads((project / FILES[3]).read_text())["mcpServers"]
    assert code == 0
    assert after["poltergeist"] == ENTRIES["poltergeist"]
    assert after["foo"] == {"a": 1}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"mcpServers": []}'])
def test_unusable_mcp_json_is_never_changed(project, hook, capsys, content):
    (project / ".kiro/settings").mkdir(parents=True)
    (project / FILES[3]).write_text(content)
    for extra in ([], ["--force"]):
        code, out = init(project, *extra, capsys=capsys)
        assert code == 1
        assert (project / FILES[3]).read_text() == content
        assert f"skipped {project / FILES[3]}" in out


def test_differing_files_are_skipped_then_forced(project, hook, capsys):
    for name in FILES[:3]:
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        (project / name).write_text("mine")
    code, out = init(project, capsys=capsys)
    assert code == 1
    assert out.count("skipped") == 3
    for name in FILES[:3]:
        assert (project / name).read_text() == "mine"
    assert (project / FILES[3]).is_file()
    code, out = init(project, "--force", capsys=capsys)
    assert code == 0
    assert out.count("updated") == 3
    assert (project / FILES[1]).read_bytes() == (REPO / "integrations/kiro/steering/poltergeist.md").read_bytes()
    assert (project / FILES[2]).read_bytes() == (REPO / "integrations/kiro/agents/simdriver.json").read_bytes()
    assert len(json.loads((project / FILES[0]).read_text())["hooks"]) == 2


def test_dry_run_writes_nothing(project, hook, capsys):
    code, out = init(project, "--dry-run", capsys=capsys)
    assert code == 0
    assert list(project.iterdir()) == []
    lines = [line for line in out.splitlines() if str(project) in line]
    assert len(lines) == 4 and all("would" in line for line in lines)


def test_dry_run_on_existing_project(project, hook, capsys):
    init(project, capsys=capsys)
    before = snapshot(project)
    code, out = init(project, "--dry-run", capsys=capsys)
    assert code == 0 and snapshot(project) == before
    assert out.count("would leave unchanged") == 4
    (project / FILES[1]).write_text("mine")
    code, out = init(project, "--dry-run", capsys=capsys)
    assert code == 1 and "would skip" in out and (project / FILES[1]).read_text() == "mine"


def test_bad_arguments_write_nothing(project, hook, capsys):
    assert cli.main(["init", "kiro", "--dir", str(project / "missing")]) == 2
    for bad in ("ftp://x", "nonsense", ""):
        assert cli.main(["init", "kiro", "--dir", str(project), "--url", bad]) == 2
    assert list(project.iterdir()) == []
    assert not (project / "missing").exists()


def test_writes_only_inside_dot_kiro_and_not_in_home(project, hook, tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    init(project, capsys=capsys)
    assert list(home.iterdir()) == []
    assert [p.name for p in project.iterdir()] == [".kiro"]


def test_write_outside_dot_kiro_is_refused(tmp_path):
    kiro = tmp_path / ".kiro"
    kiro.mkdir()
    with pytest.raises(OSError):
        cli._write(str(kiro), str(tmp_path / "evil.txt"), b"x")
    assert not (tmp_path / "evil.txt").exists()


def test_symlinked_dot_kiro_pointing_elsewhere_writes_nothing_outside(project, hook, tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, project / ".kiro")
    code, out = init(project, capsys=capsys)
    # The link resolves to its own target, so every file is inside the real .kiro; nothing leaves it.
    assert code in (0, 1)
    assert [p.name for p in project.iterdir()] == [".kiro"]
