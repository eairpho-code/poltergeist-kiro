"""The 'try it yourself' change to demo/index.html (spec: .kiro/specs/demo-try-it)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "demo" / "index.html").read_text()


def element(tag, ident):
    """(classes, visible text) of <tag id="ident" ...>...</tag>."""
    m = re.search(r'<%s\s+id="%s"([^>]*)>(.*?)</%s>' % (tag, ident, tag), HTML, re.S)
    assert m, "no <%s id=%r> in the page" % (tag, ident)
    cls = re.search(r'class="([^"]*)"', m.group(1))
    text = re.sub(r"<[^>]+>", "", m.group(2))
    return (cls.group(1).split() if cls else []), re.sub(r"\s+", " ", text).strip()


def max_height_blocks():
    blocks = []
    for m in re.finditer(r"@media\s*\([^)]*max-height[^)]*\)\s*\{", HTML):
        depth, i = 1, m.end()
        while i < len(HTML) and depth:
            depth += {"{": 1, "}": -1}.get(HTML[i], 0)
            i += 1
        blocks.append(HTML[m.start():i])
    return blocks


def labels(call):
    """Run the labels block in Node and return the JSON of `call` (a JS expression)."""
    if shutil.which("node") is None:
        pytest.skip("Node.js is needed")
    m = re.search(r"// <labels>\n(.*?)// </labels>", HTML, re.S)
    assert m, "the page has no // <labels> ... // </labels> block"
    script = (
        "const L = (function () {\n%s\nreturn {agentButtonLabel, agentButtonAction,"
        " introStatus, autoDoneStatus};\n})();\nconsole.log(JSON.stringify(%s));"
    ) % (m.group(1), call)
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --- reading the page -------------------------------------------------------

def test_the_two_buttons_have_the_new_names_and_looks():
    agent_cls, agent_text = element("button", "agentBtn")
    auto_cls, auto_text = element("button", "autoBtn")
    assert agent_text == "Try it yourself"
    assert auto_text == "Watch the story"
    assert "primary" in agent_cls
    assert "primary" not in auto_cls
    assert element("button", "resetBtn")[1] == "Reset"


@pytest.mark.parametrize("old", ["Agent step", "Play the story"])
def test_the_old_button_names_are_gone(old):
    assert old not in HTML


def test_the_other_labels_remain():
    assert "Next step" in HTML and "Replay" in HTML


@pytest.mark.parametrize("ident", ["agentBtn", "autoBtn", "resetBtn", "window", "screen", "app"])
def test_the_ids_appear_exactly_once(ident):
    assert HTML.count('id="%s"' % ident) == 1


def test_the_status_line_tells_the_visitor_what_to_do_first():
    _, status = element("div", "window")
    assert "Try it yourself" in status
    assert "click where the agent should have tapped" in status


def test_the_numbered_steps_use_the_new_names():
    steps = re.search(r'<ol class="steps">(.*?)</ol>', HTML, re.S)
    assert steps and "Try it yourself" in steps.group(1)


def test_no_max_height_media_query_touches_the_status_line():
    for block in max_height_blocks():
        assert "#window" not in block and ".status" not in block


def test_the_760_pixel_rule_no_longer_hides_the_steps():
    assert not re.search(r"max-height:\s*760px[^}]*\{[^}]*\.steps", HTML)
    assert "max-height: 760px" not in HTML


def test_core_and_app_blocks_are_still_there():
    for name in ("core", "app"):
        assert re.search(r"// <%s>\n.*?// </%s>" % (name, name), HTML, re.S)


# --- running the labels block in Node ---------------------------------------

@pytest.mark.parametrize(
    "done, steps, auto, expected",
    [
        (False, 0, False, "Try it yourself"),
        (False, 1, False, "Next step"),
        (False, 4, True, "Next step"),
        (True, 5, False, "Replay"),
        (True, 5, True, "Try it yourself"),
    ],
)
def test_the_agent_button_label(done, steps, auto, expected):
    call = "L.agentButtonLabel(%s, %d, %s)" % (str(done).lower(), steps, str(auto).lower())
    assert labels(call) == expected


def test_pressing_the_agent_button_when_done_restarts_in_one_press():
    assert labels("L.agentButtonAction(true)") == "restart"
    assert labels("L.agentButtonAction(false)") == "step"


def test_the_intro_status_names_the_button_and_the_window():
    text = labels("L.introStatus('15s')")
    assert "15s" in text and "Try it yourself" in text
    assert "click where the agent should have tapped" in text


def test_the_end_of_the_automatic_story_invites_the_visitor():
    text = labels("L.autoDoneStatus()")
    assert "ghost" in text.lower() and "did the correcting" in text
    assert "Try it yourself" in text


def test_the_countdown_writes_nothing_once_the_task_is_done():
    m = re.search(r"function tickCountdown\(\) \{(.*?)\n      \}\n", HTML, re.S)
    assert m, "no tickCountdown function in the page"
    body = m.group(1)
    guard = body.find("taskDone(S.app)")
    first_write = body.find("setStatus(")
    assert guard != -1, "tickCountdown does not check whether the task is done"
    assert guard < first_write, "the done check must come before any setStatus"
    assert "return;" in body[guard:first_write]
