# Design Document

## Overview

Three small changes. The log computes the scale problem over everything. A pure function decides whether a scale problem is news. The watcher and the hook remember what they last reported and use that function.

## Components

### `poltergeist/action_log.py`: `ActionLog.get_human_actions`

Detection already runs over the whole sorted log (`all_mismatches`). Keep filtering `human_actions` and `mismatches` by the cursor, and compute `detect_scale_problem(all_mismatches)` instead of `detect_scale_problem(mismatches)`. Without a cursor nothing changes.

### `poltergeist/activity.py`: `scale_changed`

```python
SCALE_CHANGE_THRESHOLD = 0.05

def scale_changed(previous: Optional[dict], current: Optional[dict]) -> bool: ...
```

- `current is None` gives `False`.
- `previous is None` gives `True`.
- Otherwise `True` when `abs(current[k] - previous[k]) > SCALE_CHANGE_THRESHOLD * abs(previous[k])` for `k` in `scale_x`, `scale_y`. The comparison is strict and uses plain floating point arithmetic, and the demo does the same, so that both give the same answer for every input.

### The watcher (`poltergeist/watch.py`)

`Watcher` keeps `self._reported_scale: Optional[dict]`.

- `start()`: after fetching, `self._reported_scale = payload.get("coordinate_scale_problem")`.
- `poll()`: let `problem = payload.get("coordinate_scale_problem")`. If `scale_changed(self._reported_scale, problem)`, keep the problem in the payload and set `self._reported_scale = problem`. Otherwise describe a copy of the payload whose `coordinate_scale_problem` is `None`, and when `problem is None` also set `self._reported_scale = None`. Then `describe_activity` as before.

### The hook (`poltergeist/claude_hook.py`)

`CursorStore` keeps one JSON file. `save(cursor)` reads the existing data and writes it back with the new `cursor`, keeping `scale`. `load_scale()` returns `{"scale_x": ..., "scale_y": ...}` or `None`. `save_scale(problem)` writes `scale` with only those two numbers, or removes the key.

`handle_event`:

- First call (`previous is None`): save the server time, and `save_scale(payload.get("coordinate_scale_problem"))`. Return `None`.
- Later calls: `problem = payload.get("coordinate_scale_problem")`. If `scale_changed(cursor.load_scale(), problem)`, keep it and `save_scale(problem)`. Otherwise drop it from the payload that is described, and when `problem is None` call `save_scale(None)`. Cursor handling for human actions is as before. Return `None` when there are no lines.

### The demo (`demo/index.html`)

Add `scaleChanged(previous, current)` inside the core block: `current` null gives false, `previous` null gives true, otherwise the strict 5 percent rule on `scaleX` and `scaleY`. In `hearStep`, keep the last scale that was told to the agent in the app state (`S.toldScale`), tell the scale problem only when `scaleChanged(S.toldScale, snap.scale)`, set `S.toldScale` when told, and clear it on reset and when `snap.scale` is null. Add the rule to the harness of `demo/check_port.py` (already done there).

## Testing

`tests/test_incremental_scale.py` holds the tests of this change. `demo/check_port.py` holds the parity check.
