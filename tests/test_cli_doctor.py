"""Tests for ``poltergeist doctor`` (poltergeist/cli.py)."""

import json
import re
import stat
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from poltergeist import cli

NAMES = ["server", "hooks", "steering", "agent", "mcp", "observer", "simulator", "idb", "kiro"]


class _Handler(BaseHTTPRequestHandler):
    body = b'{"human_actions": []}'

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _script(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def tools(tmp_path, monkeypatch):
    """A PATH that holds only fake tools; returns the folder."""
    bin_dir = tmp_path / "fakes"
    bin_dir.mkdir()
    _script(bin_dir / "xcrun", '#!/bin/sh\necho "  iPhone (ABCD) (Booted)"\n')
    _script(bin_dir / "pgrep", "#!/bin/sh\nexit 0\n")
    _script(bin_dir / "idb", '#!/bin/sh\necho "iPhone | ABCD | Booted"\n')
    _script(bin_dir / "kiro-cli", '#!/bin/sh\necho "kiro-cli 3"\n')
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("IOS_SIMULATOR_MCP_IDB_PATH", raising=False)
    return bin_dir


@pytest.fixture
def project(tmp_path, server, tools, monkeypatch):
    hook_dir = tmp_path / "venv"
    hook_dir.mkdir()
    _script(hook_dir / "poltergeist-kiro-hook", "#!/bin/sh\n")
    monkeypatch.setattr(sys, "executable", str(hook_dir / "python"))
    proj = tmp_path / "proj"
    proj.mkdir()
    assert cli.main(["init", "kiro", "--dir", str(proj), "--url", server]) == 0
    return proj


def run(capsys, proj, url):
    code = cli.main(["doctor", "--dir", str(proj), "--url", url])
    return code, capsys.readouterr().out


def statuses(out):
    return {name: status for status, name in re.findall(r"^\[(ok|warn|fail)\] (\w+):", out, re.M)}


def test_everything_in_place(capsys, project, server):
    code, out = run(capsys, project, server)
    assert code == 0
    assert list(statuses(out)) == NAMES
    assert set(statuses(out).values()) == {"ok"}
    assert "9 ok, 0 warn, 0 fail" in out
    assert "Accessibility" in out and "Input Monitoring" in out


def test_changes_nothing(capsys, project, server):
    def snapshot():
        return {str(p): p.read_bytes() for p in project.rglob("*") if p.is_file()}

    before = snapshot()
    run(capsys, project, server)
    assert snapshot() == before


def test_defaults_to_current_folder(capsys, project, server, monkeypatch):
    monkeypatch.chdir(project)
    assert cli.main(["doctor", "--url", server]) == 0
    assert statuses(capsys.readouterr().out)["hooks"] == "ok"


def test_server_down(capsys, project):
    code, out = run(capsys, project, "http://127.0.0.1:1")
    assert code == 1
    assert statuses(out)["server"] == "fail"
    assert "poltergeist-server" in out
    assert len(statuses(out)) == 9


def test_server_without_human_actions(capsys, project, server, monkeypatch):
    monkeypatch.setattr(_Handler, "body", b'{"other": 1}')
    code, out = run(capsys, project, server)
    assert statuses(out)["server"] == "fail" and code == 1


def _hook_file(project):
    return project / ".kiro" / "hooks" / "poltergeist.json"


def test_hook_command_missing_file(capsys, project, server):
    data = json.loads(_hook_file(project).read_text())
    data["hooks"][0]["action"]["command"] = "/nonexistent/poltergeist-kiro-hook --url " + server
    _hook_file(project).write_text(json.dumps(data))
    code, out = run(capsys, project, server)
    assert statuses(out)["hooks"] == "fail" and code == 1


def test_hook_command_relative(capsys, project, server):
    data = json.loads(_hook_file(project).read_text())
    data["hooks"][0]["action"]["command"] = "poltergeist-kiro-hook --url " + server
    _hook_file(project).write_text(json.dumps(data))
    assert statuses(run(capsys, project, server)[1])["hooks"] == "fail"


def test_hook_command_not_executable(capsys, project, server, tmp_path):
    plain = tmp_path / "plain"
    plain.write_text("x")
    data = json.loads(_hook_file(project).read_text())
    data["hooks"][0]["action"]["command"] = f"{plain} --url {server}"
    _hook_file(project).write_text(json.dumps(data))
    assert statuses(run(capsys, project, server)[1])["hooks"] == "fail"


def test_hook_file_broken_or_missing_or_incomplete(capsys, project, server):
    _hook_file(project).write_text("{not json")
    assert statuses(run(capsys, project, server)[1])["hooks"] == "fail"
    _hook_file(project).write_text(json.dumps({"hooks": [{"trigger": "PreToolUse"}]}))
    assert statuses(run(capsys, project, server)[1])["hooks"] == "fail"
    _hook_file(project).unlink()
    assert statuses(run(capsys, project, server)[1])["hooks"] == "fail"


def test_hook_url_mismatch_warns_in_detail(capsys, project, server):
    code, out = run(capsys, project, "http://127.0.0.1:1")
    line = next(l for l in out.splitlines() if l.startswith("[ok] hooks"))
    assert "warning" in line and "--url" in line


def test_quoted_hook_path_with_space(capsys, tmp_path, server, tools, monkeypatch):
    hook_dir = tmp_path / "my venv"
    hook_dir.mkdir()
    _script(hook_dir / "poltergeist-kiro-hook", "#!/bin/sh\n")
    monkeypatch.setattr(sys, "executable", str(hook_dir / "python"))
    proj = tmp_path / "p"
    proj.mkdir()
    cli.main(["init", "kiro", "--dir", str(proj), "--url", server])
    capsys.readouterr()
    assert statuses(run(capsys, proj, server)[1])["hooks"] == "ok"


def test_steering_and_agent_are_warnings(capsys, project, server):
    (project / ".kiro" / "steering" / "poltergeist.md").unlink()
    (project / ".kiro" / "agents" / "simdriver.json").write_text("{bad")
    code, out = run(capsys, project, server)
    got = statuses(out)
    assert got["steering"] == "warn" and got["agent"] == "warn"
    assert code == 0


def test_mcp_failures(capsys, project, server):
    path = project / ".kiro" / "settings" / "mcp.json"
    original = json.loads(path.read_text())
    broken = json.loads(json.dumps(original))
    del broken["mcpServers"]["ios-simulator"]
    path.write_text(json.dumps(broken))
    assert statuses(run(capsys, project, server)[1])["mcp"] == "fail"
    other = json.loads(json.dumps(original))
    other["mcpServers"]["poltergeist"] = {"url": "http://127.0.0.1:1/mcp"}
    path.write_text(json.dumps(other))
    assert statuses(run(capsys, project, server)[1])["mcp"] == "fail"
    path.write_text("{bad")
    assert statuses(run(capsys, project, server)[1])["mcp"] == "fail"
    path.unlink()
    assert statuses(run(capsys, project, server)[1])["mcp"] == "fail"


def test_trailing_slash_url_matches(capsys, project, server):
    assert statuses(run(capsys, project, server + "/")[1])["mcp"] == "ok"


def test_unhappy_environment_is_only_warnings(capsys, project, server, tools):
    _script(tools / "pgrep", "#!/bin/sh\nexit 1\n")
    _script(tools / "xcrun", "#!/bin/sh\necho ''\n")
    (tools / "idb").unlink()
    (tools / "kiro-cli").unlink()
    code, out = run(capsys, project, server)
    got = statuses(out)
    assert {got[n] for n in ("observer", "simulator", "idb", "kiro")} == {"warn"}
    assert code == 0 and "5 ok, 4 warn, 0 fail" in out


def test_no_tools_no_traceback(capsys, project, server, tools):
    for f in tools.iterdir():
        f.unlink()
    code, out = run(capsys, project, server)
    assert "Traceback" not in out
    assert {statuses(out)[n] for n in ("observer", "simulator", "idb", "kiro")} == {"warn"}


def test_idb_environment_variable(capsys, project, server, tools, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _script(elsewhere / "idb", '#!/bin/sh\necho "x"\n')
    (tools / "idb").unlink()
    monkeypatch.setenv("IOS_SIMULATOR_MCP_IDB_PATH", str(elsewhere / "idb"))
    assert statuses(run(capsys, project, server)[1])["idb"] == "ok"


def test_idb_listing_nothing_mentions_connect(capsys, project, server, tools):
    _script(tools / "idb", "#!/bin/sh\nexit 0\n")
    out = run(capsys, project, server)[1]
    assert statuses(out)["idb"] == "warn" and "idb connect" in out


def test_hanging_tool_times_out(capsys, project, server, tools, monkeypatch):
    monkeypatch.setattr(cli, "COMMAND_TIMEOUT", 0.5)
    _script(tools / "xcrun", "#!/bin/sh\nsleep 30\n")
    started = time.time()
    out = run(capsys, project, server)[1]
    assert time.time() - started < 10
    assert statuses(out)["simulator"] == "warn"


def test_command_timeout_is_at_most_five_seconds():
    assert cli.COMMAND_TIMEOUT <= 5


def test_doctor_bad_arguments():
    assert cli.main(["doctor", "--bogus"]) == 2
