# Design Document

## Overview

Five small changes to existing modules, one new example file, tests and documentation. No new module. The coordinate scale rule is not touched.

```
 detect_mismatches ──▶ Mismatch (+ ratio_x, ratio_y) ──▶ GET /human-actions
        │                       │                    └─▶ get_human_actions (MCP)
        │                       └─▶ describe_mismatch (+ ratio sentence)
        └─ window: POLTERGEIST_MISMATCH_WINDOW_SECONDS (default 5)

 Kiro ─ PreToolUse ─▶ /ABS/PATH/poltergeist-kiro-hook --url ADDRESS ─▶ POST /agent-click
```

## The ratio of a pair

- `Mismatch` in `poltergeist/action_log.py` gets two fields, `ratio_x: float | None = None` and `ratio_y: float | None = None`, after the existing five. The defaults keep every existing construction working.
- `detect_mismatches` in `poltergeist/detection.py` fills them from the normalized coordinates: `agent / human`, or `None` when `abs(human) < 1.0`. The threshold is the one the scale rule uses to skip a sample; the code shares the constant rather than repeating the number.
- The route and the tool already serialize the `Mismatch`, so both carry the new keys without further change. `server.py` changes only if serialization lists fields by hand.
- The scale-problem detection is not edited.

## The sentence

`describe_mismatch` in `poltergeist/activity.py` appends, right after the offset text, `, ratio x1.50 / y1.50 for this pair alone`.

- Each value is formatted with two decimals. An unknown value (missing key, `None`, or not a finite number) is written `?` after its axis letter, as `x?`.
- Both unknown: nothing is appended. A payload without the keys is the both-unknown case, so old payloads read as before.
- The words `None` and `nan` never appear. The sentence says nothing about a scale problem; that sentence belongs to the scale-problem description only.

## The window

`detection.py` keeps `MISMATCH_WINDOW_SECONDS` as a module constant, now set at import by a small function that reads `POLTERGEIST_MISMATCH_WINDOW_SECONDS`. A value that does not parse as a float, is not finite or is not above 0 is ignored, a warning is logged, and 5 is used. The pairing comparison stays `gap < MISMATCH_WINDOW_SECONDS`, read from the module at call time so `demo/check_port.py` can still patch it.

## The recorder address

`poltergeist/kiro_hook.py`: `main()` reads `sys.argv[1:]` and looks for `--url VALUE` or `--url=VALUE`. The first non-empty value wins; any other argument, and a `--url` with no value, is skipped. The base URL is the argument, else `POLTERGEIST_URL`, else `http://127.0.0.1:8000`, with a trailing slash removed. Argument parsing sits inside the existing catch-all, so the exit code stays 0 and nothing is printed. `argparse` is not used because it prints and exits on bad input.

## Example files

- `integrations/kiro/hooks/poltergeist.json`: the command of the `PreToolUse` hook becomes `/ABSOLUTE/PATH/TO/poltergeist-kiro-hook --url http://127.0.0.1:8000`.
- `integrations/kiro/agents/simdriver.json`: the agent configuration of the brief, for `--agent simdriver`.
- `integrations/kiro/steering/poltergeist.md` may mention the ratio of a pair, saying that one pair is not yet a scale problem.

## The demo

`demo/index.html` gets the same ratio computation (with the same 1.0 threshold) and the same sentence formatting in its JavaScript core, and shows `ratio_x` and `ratio_y` in the JSON panel. `demo/check_port.py` compares the ratio and the sentence with Python for a set of pairs, including a human coordinate below 1.0.

## Documentation

`README.md` and `docs/usage.md` cover Requirement 6 in full: the ratio fields and the sentence, the variable in the environment table, `--url`, the settings path `.kiro/settings/mcp.json`, the non-interactive trust problem and the `--agent` fix, IDB, the scale of `ios-simulator-mcp` screenshots, what was checked, and the observer permissions. The "not run" sentence is replaced.

## Tests

- Ratio: values, the 1.0 threshold, defaults, route and tool return the keys.
- Sentence: both known, one unknown, both unknown, old payload, no `None` or `nan`, no scale-problem wording.
- Window: default, a valid value, and each invalid value (text, `nan`, `inf`, 0, negative) falling back to 5; a gap equal to the window does not pair.
- Recorder: `--url`, `--url=`, precedence over `POLTERGEIST_URL`, ignored arguments, `--url` without a value; exit code 0 and silence.
- Example files: `tests/test_kiro_hook.py` is updated for the new command; the agent example is checked.
- No existing test other than `tests/test_kiro_hook.py` is edited.
