"""Tests for the ratio of a pair and the configurable pairing window."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from poltergeist.action_log import ClickAction, Mismatch
from poltergeist.activity import describe_mismatch
from poltergeist.detection import detect_mismatches
from poltergeist.server import _mismatch_to_dict

BASE = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)


def click(actor, seconds, x, y):
    stamp = (BASE + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return ClickAction(
        timestamp=stamp, actor=actor, normalized_x=x, normalized_y=y, raw_x=x,
        raw_y=y, coordinate_space="device_points", scale_factor=1.0,
    )


def pair(agent_xy, human_xy, gap=1.0):
    return detect_mismatches(
        [click("agent", 0, *agent_xy), click("human", gap, *human_xy)]
    )[0]


def payload(agent_xy, human_xy):
    return _mismatch_to_dict(pair(agent_xy, human_xy))


def test_ratio_of_a_pair():
    m = pair((150, 300), (100, 200))
    assert m.ratio_x == 1.5 and m.ratio_y == 1.5


def test_ratio_is_none_below_threshold():
    m = pair((100, 300), (0.5, 30))
    assert m.ratio_x is None
    assert m.ratio_y == 10.0
    assert pair((100, 300), (-0.99, 30)).ratio_x is None


def test_ratio_threshold_uses_absolute_value():
    m = pair((100, 300), (-2, -50))
    assert m.ratio_x == -50.0 and m.ratio_y == -6.0


def test_mismatch_with_five_fields_still_builds():
    a, h = click("agent", 0, 1, 1), click("human", 1, 2, 2)
    m = Mismatch(agent_click=a, human_click=h, offset_x=1, offset_y=1, distance=1.4)
    assert m.ratio_x is None and m.ratio_y is None


def test_route_dict_has_ratios():
    d = payload((150, 300), (100, 200))
    assert d["ratio_x"] == 1.5 and d["ratio_y"] == 1.5
    assert payload((100, 300), (0.5, 30))["ratio_x"] is None


def test_sentence_carries_ratio():
    text = describe_mismatch(payload((150, 300), (100, 200)))
    assert "offset (-50.0, -100.0), ratio x1.50 / y1.50 for this pair alone:" in text
    assert "scale problem" not in text.lower()


def test_sentence_with_one_unknown_ratio():
    text = describe_mismatch(payload((100, 300), (0.5, 30)))
    assert "ratio x? / y10.00 for this pair alone" in text
    for word in ("None", "nan", "null"):
        assert word not in text


def test_sentence_with_no_known_ratio_adds_nothing():
    p = payload((150, 300), (100, 200))
    p["ratio_x"] = p["ratio_y"] = None
    assert "ratio" not in describe_mismatch(p)


def test_sentence_without_ratio_keys():
    p = payload((150, 300), (100, 200))
    del p["ratio_x"], p["ratio_y"]
    assert "ratio" not in describe_mismatch(p)


def test_sentence_survives_nan_ratio():
    p = payload((150, 300), (100, 200))
    p["ratio_x"] = float("nan")
    text = describe_mismatch(p)
    assert "nan" not in text and "x? / y1.50" in text


WINDOW_PROBE = """
import json
from poltergeist import detection
print(json.dumps(detection.MISMATCH_WINDOW_SECONDS))
"""


def window(value):
    env = dict(os.environ)
    env.pop("POLTERGEIST_MISMATCH_WINDOW_SECONDS", None)
    if value is not None:
        env["POLTERGEIST_MISMATCH_WINDOW_SECONDS"] = value
    out = subprocess.run(
        [sys.executable, "-c", WINDOW_PROBE], env=env, capture_output=True, text=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1]), out.stderr


def test_window_default_is_five():
    assert window(None)[0] == 5


def test_window_from_environment():
    assert window("10")[0] == 10
    assert window("0.5")[0] == 0.5


def test_invalid_window_falls_back_with_warning():
    for bad in ("abc", "0", "-3", "nan", "inf", ""):
        value, err = window(bad)
        assert value == 5, bad
        assert "POLTERGEIST_MISMATCH_WINDOW_SECONDS" in err, bad


def test_window_boundary_is_exclusive(monkeypatch):
    from poltergeist import detection

    monkeypatch.setattr(detection, "MISMATCH_WINDOW_SECONDS", 2.0)
    assert len(detect_mismatches([click("agent", 0, 1, 1), click("human", 1.9, 2, 2)])) == 1
    assert len(detect_mismatches([click("agent", 0, 1, 1), click("human", 2.0, 2, 2)])) == 0
