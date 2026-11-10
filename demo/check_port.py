"""Check that the JavaScript in demo/index.html behaves like the Python detection rules.

Generates random click/drag logs with 5, 15 and 30 second windows, runs both implementations and compares which
agent clicks pair with which human clicks, the scale problem, and the sentences
an agent would be told. Needs Node.js. Run from the repository root:

    python demo/check_port.py
"""

import json
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from poltergeist.action_log import ClickAction, UIElement  # noqa: E402
from poltergeist.activity import describe_action, describe_mismatch, scale_changed  # noqa: E402
from poltergeist import detection  # noqa: E402
from poltergeist.detection import detect_mismatches, detect_scale_problem  # noqa: E402

BASE_MS = 1_780_000_000_000
SCENARIOS = 3000

HARNESS = """
const fs = require('fs');
%CORE%
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const scenarios = input.scenarios;
const results = scenarios.map(scenario => {
  const actions = scenario.rows.map(r => {
    const a = makeAction(r.actor, r.kind, r.x, r.y, r.ex, r.ey, r.scale, r.t);
    a.role = r.role;
    a.label = r.label;
    return a;
  });
  const mism = detectMismatches(actions, scenario.windowMs);
  const scale = detectScaleProblem(mism);
  const humans = actions.filter(a => a.actor === 'human').sort((p, q) => p.t - q.t);
  return {
    pairs: mism.map(m => [actions.indexOf(m.agent), actions.indexOf(m.human), m.offX, m.offY, m.distance]),
    scale,
    actionLines: humans.map(a => describeAction(a, a.role)),
    mismatchLines: mism.map(describeMismatch),
  };
});
const changed = input.pairs.map(p => scaleChanged(p[0], p[1]));
process.stdout.write(JSON.stringify({ results, changed }));
"""


def extract_core() -> str:
    html = (ROOT / "demo" / "index.html").read_text()
    match = re.search(r"// <core>\n(.*?)// </core>", html, re.S)
    if not match:
        sys.exit("could not find the <core> block in demo/index.html")
    return match.group(1)


def random_scenario(rng: random.Random) -> list:
    rows = []
    if rng.random() < 0.35:
        # A consistent scale error, so the scale rule is exercised too.
        ratio = rng.choice([1.5, 2.0, 3.0])
        noise = rng.choice([0.0, 0.02, 0.08, 0.2])
        for i in range(rng.randint(2, 6)):
            hx, hy = rng.uniform(5, 300), rng.uniform(5, 600)
            t = 1000 + i * 7000
            jitter = lambda: 1 + rng.uniform(-noise, noise)
            rows.append(dict(actor="agent", kind="click", x=hx * ratio * jitter(), y=hy * ratio * jitter(), scale=1, t=t))
            rows.append(dict(actor="human", kind="click", x=hx, y=hy, scale=1, t=t + rng.choice([500, 2000, 4750, 12000, 14750])))
    else:
        for _ in range(rng.randint(0, 12)):
            rows.append(dict(
                actor=rng.choice(["agent", "human"]),
                kind="drag" if rng.random() < 0.15 else "click",
                x=rng.choice([0.5, rng.uniform(0, 430)]),
                y=rng.choice([0.5, rng.uniform(0, 932)]),
                scale=rng.choice([1, 2, 3]),
                t=rng.randrange(0, 40000, 250),  # multiples of 250 ms make exact window-sized gaps and ties common
            ))
    for r in rows:
        r["ex"] = rng.uniform(0, 430 * r["scale"])
        r["ey"] = rng.uniform(0, 932 * r["scale"])
        r["role"] = rng.choice([None, "button", "text", "switch", "text_field"]) if r["actor"] == "human" else None
        r["label"] = rng.choice([None, "", "I", "Candle I", "2 of 3 candles lit"]) if r["role"] else None
        r["t"] += BASE_MS
    rng.shuffle(rows)
    return rows


def to_python(rows: list) -> list:
    actions = []
    for r in rows:
        stamp = (datetime.fromtimestamp(r["t"] / 1000, timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        action = ClickAction(
            timestamp=stamp, actor=r["actor"],
            normalized_x=r["x"] / r["scale"], normalized_y=r["y"] / r["scale"],
            raw_x=r["x"], raw_y=r["y"], coordinate_space="device_points", scale_factor=r["scale"],
            ui_element=UIElement(role=r["role"], label=r["label"]) if r["role"] else None,
            kind=r["kind"],
        )
        if r["kind"] == "drag":
            action.end_x, action.end_y = r["ex"] / r["scale"], r["ey"] / r["scale"]
        actions.append(action)
    return actions


def as_dict(action: ClickAction) -> dict:
    return {
        "timestamp": action.timestamp, "normalized_x": action.normalized_x, "normalized_y": action.normalized_y,
        "kind": action.kind, "end_x": action.end_x, "end_y": action.end_y,
        "ui_element": {"role": action.ui_element.role, "label": action.ui_element.label} if action.ui_element else None,
    }


def random_scale_pairs(rng: random.Random, count: int = 2000) -> list:
    """Pairs (previous, current) of scale problems or None, for scale_changed."""
    factors = [1.0, 1.0, 1.04, 1.049, 1.05, 1.051, 1.06, 0.96, 0.95, 0.94, 0.9, 1.2]
    pairs = []
    for _ in range(count):
        previous = None if rng.random() < 0.2 else (rng.uniform(1, 3), rng.uniform(1, 3))
        if rng.random() < 0.15:
            current = None
        elif previous is None:
            current = (rng.uniform(1, 3), rng.uniform(1, 3))
        else:
            current = (previous[0] * rng.choice(factors), previous[1] * rng.choice(factors))
        pairs.append((previous, current))
    return pairs


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def main() -> int:
    rng = random.Random(20261103)
    scenarios = [{"rows": random_scenario(rng), "windowMs": rng.choice([5000, 5000, 15000, 30000])} for _ in range(SCENARIOS)]
    pairs = random_scale_pairs(rng)
    js_pairs_input = [[None if p is None else {"scaleX": p[0], "scaleY": p[1]} for p in pair] for pair in pairs]

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "run.js"
        script.write_text(HARNESS.replace("%CORE%", extract_core()))
        result = subprocess.run(
            ["node", str(script)], input=json.dumps({"scenarios": scenarios, "pairs": js_pairs_input}),
            capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        return 1
    parsed = json.loads(result.stdout)
    js_results, js_changed = parsed["results"], parsed["changed"]

    paired = scaled = 0
    failures = []
    for number, (scenario, js) in enumerate(zip(scenarios, js_results)):
        actions = to_python(scenario["rows"])
        detection.MISMATCH_WINDOW_SECONDS = scenario["windowMs"] / 1000
        mismatches = detect_mismatches(actions)
        detection.MISMATCH_WINDOW_SECONDS = 5.0
        problem = detect_scale_problem(mismatches)

        position = lambda target: next(i for i, a in enumerate(actions) if a is target)  # identity: equal actions can repeat
        py_pairs = [(position(m.agent_click), position(m.human_click)) for m in mismatches]
        js_pairs = [(p[0], p[1]) for p in js["pairs"]]
        if py_pairs != js_pairs:
            failures.append((number, "pairs differ", py_pairs, js_pairs))
            continue
        for m, p in zip(mismatches, js["pairs"]):
            if not (close(m.offset_x, p[2]) and close(m.offset_y, p[3]) and close(m.distance, p[4])):
                failures.append((number, "offsets differ", m, p))

        if (problem is None) != (js["scale"] is None):
            failures.append((number, "scale problem presence differs", problem, js["scale"]))
        elif problem is not None:
            s = js["scale"]
            if not (close(problem.scale_x, s["scaleX"]) and close(problem.scale_y, s["scaleY"]) and problem.sample_size == s["sampleSize"]):
                failures.append((number, "scale numbers differ", problem, s))

        humans = sorted((a for a in actions if a.actor == "human"), key=lambda a: a.timestamp)
        if [describe_action(as_dict(a)) for a in humans] != js["actionLines"]:
            failures.append((number, "action sentences differ"))
        py_lines = [describe_mismatch({
            "agent_click": as_dict(m.agent_click), "human_click": as_dict(m.human_click),
            "offset_x": m.offset_x, "offset_y": m.offset_y}) for m in mismatches]
        if py_lines != js["mismatchLines"]:
            failures.append((number, "mismatch sentences differ", py_lines, js["mismatchLines"]))

        paired += bool(mismatches)
        scaled += problem is not None

    for number, (pair, js) in enumerate(zip(pairs, js_changed)):
        as_problem = lambda p: None if p is None else {"scale_x": p[0], "scale_y": p[1]}
        if scale_changed(as_problem(pair[0]), as_problem(pair[1])) != js:
            failures.append((number, "scale_changed differs", pair, js))

    print(f"{len(scenarios)} random logs: {paired} with pairs, {scaled} with a scale problem; {len(pairs)} scale_changed pairs")
    if failures:
        print(f"{len(failures)} differences, first: {failures[0]}")
        return 1
    print("the JavaScript matches the Python implementation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
