# Requirements Document

## Introduction

Filming Poltergeist against a real model showed that the coordinate scale problem is almost never reported to the agent. `get_human_actions` and `GET /human-actions` accept a `since` cursor and then compute the scale problem from only the mismatches that fall after the cursor. The watcher and the Claude Code hook both read with a cursor, so a scale problem shows up only when three corrections happen between two reads. In real use they arrive one at a time. A model that read the log without a cursor saw `coordinate_scale_problem` with three samples; the same model reading with a cursor saw `null` and never learned its coordinates were on the wrong scale.

This change makes the scale problem a property of the whole log, and makes the watcher and the hook tell the agent about it once, when it first appears or when it changes, not on every read.

## Glossary

- **Cursor**: the `since` timestamp of `get_human_actions` and `GET /human-actions`.
- **Whole log**: every action the server holds, regardless of the cursor.
- **Reported scale**: the scale problem that a watcher or a hook last told the agent about: its `scale_x` and `scale_y`.
- **Changed**: the new scale problem differs from the reported scale by more than 5 percent, relative to the reported scale, in `scale_x` or in `scale_y`.

## Requirements

### Requirement 1: The scale problem belongs to the whole log

**User Story:** As an agent that reads the log in steps, I want to be told about a scale problem as soon as the whole log shows one, so that I can fix my coordinates.

#### Acceptance Criteria

1. WHEN `get_human_actions` or `GET /human-actions` is given a cursor, THE server SHALL compute `coordinate_scale_problem` from all mismatches of the whole log, not only from the returned ones.
2. WHEN a cursor is given, `human_actions` and `mismatches` SHALL still contain only the human actions after the cursor and the mismatches whose human click is after the cursor, as before. The cursor is exclusive, as before.
3. WHEN no cursor is given, THE result SHALL be exactly what it was before this change.
4. A cursor later than every action SHALL give empty `human_actions` and `mismatches`, and the scale problem of the whole log.
5. THE rule that names a scale problem (at least three samples, relative spread at most 10 percent, positive mean) SHALL NOT change.

### Requirement 2: Say it once, then say it again only when it changes

**User Story:** As an agent, I do not want to be told the same scale problem on every tool call, but I do want to hear when it changes.

#### Acceptance Criteria

1. THE module `poltergeist.activity` SHALL provide `scale_changed(previous, current)`. It returns `True` only when `current` is a scale problem and either `previous` is `None` or `scale_x` or `scale_y` of `current` differs from `previous` by more than 5 percent of `previous`. It returns `False` when `current` is `None`. `previous` and `current` are the dictionaries of the read route (`scale_x`, `scale_y`, and other keys that it ignores).
2. THE watcher SHALL print the scale problem sentence only when `scale_changed(reported, current)` is true, and then it records `current` as the reported scale. When the read route returns no scale problem, the watcher forgets the reported scale, so that a scale problem that appears again is reported again.
3. WHEN the watcher starts, a scale problem that already exists SHALL count as reported, so that it does not replay history. Only a later change is reported.
4. THE hook SHALL follow the same rule. The reported scale SHALL be stored in the session's state file next to the cursor, so that it survives between hook calls, which are separate processes. The first call of a session still says nothing, and it records the scale problem that exists then as reported.
5. WHEN there is nothing else to say, a scale problem that is not new SHALL NOT make the watcher or the hook speak.
6. `describe_activity(payload)` SHALL keep describing the scale problem when the payload has one. The watcher and the hook decide whether the payload still has one, by removing it before they describe.

### Requirement 3: State file

**User Story:** As a maintainer, I want the hook's state to stay compatible.

#### Acceptance Criteria

1. THE state file of a session is a JSON object. It keeps the key `cursor` as before and may hold the key `scale`, an object with `scale_x` and `scale_y`.
2. `CursorStore.load()` and `CursorStore.save(cursor)` SHALL keep their signatures. `save` SHALL NOT remove a stored scale. `CursorStore.load_scale()` returns the stored scale or `None`. `CursorStore.save_scale(problem)` stores `scale_x` and `scale_y` of a scale problem, or removes the stored scale when given `None`. Neither raises on a file error.

### Requirement 4: The demo behaves like the real hook

**User Story:** As a visitor, I want the demo to show what the real hook does.

#### Acceptance Criteria

1. THE core of `demo/index.html` SHALL provide `scaleChanged(previous, current)` with the rule of Requirement 2.1, on the objects of the core (`scaleX`, `scaleY`).
2. THE demo's agent SHALL be told the scale problem by the same rule: when it first appears, and again only when it changed.
3. `demo/check_port.py` compares `scaleChanged` with `scale_changed` on random pairs.

### Requirement 5: Documentation

1. `docs/usage.md` SHALL say that the scale problem is computed from the whole log whatever the cursor is, and SHALL describe the once-then-on-change rule of the watcher and the hook and the `scale` key of the state file.
