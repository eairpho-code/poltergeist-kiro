# Design Document

## Overview

Only `demo/index.html` changes (stage 2). A new block of the script, the **labels block**, holds the small decisions that cannot be checked by reading the page: which label the agent button shows, what a press does, and the two status sentences. It sits between `// <labels>` and `// </labels>`, after `// </app>` and before the page code. It has no browser objects, so `tests/test_demo_try_it.py` cuts it out and runs it in Node, the way `demo/check_app.py` runs the app. The `// <core>` and `// <app>` blocks are not touched.

## The labels block

Constants:

- `LABEL_TRY = 'Try it yourself'`, `LABEL_NEXT = 'Next step'`, `LABEL_REPLAY = 'Replay'`.

Functions:

- `agentButtonLabel(done, stepCount, auto)` returns the text of `#agentBtn`. `done` is `taskDone(S.app)`, `stepCount` is the number of agent steps in the run, `auto` is true when the run was automatic.
  - `done` and `auto`: `Try it yourself`.
  - `done` and not `auto`: `Replay`.
  - not `done` and `stepCount === 0`: `Try it yourself`.
  - otherwise: `Next step`.
- `agentButtonAction(done)` returns `'restart'` when `done` is true, else `'step'`. `restart` means: reset, then the agent's first step, in one press.
- `introStatus(winLabel)` returns `Window: <winLabel>. Press “Try it yourself”, then click where the agent should have tapped.`
- `autoDoneStatus()` returns `The ghost did the correcting. Press “Try it yourself” to do it yourself.`

The quotes are written as `\u201C` and `\u201D` in the script, as the page does today.

## The page

- Markup: `#agentBtn` has the classes `btn primary` and the text `Try it yourself`; `#autoBtn` has the class `btn` only and the text `Watch the story`. The CSS rule `.btn.primary` (violet) stays; `.btn.agentbtn` is no longer used by the button and its rule is removed, so that the agent button takes the primary look. `#autoBtn` has the plain `.btn` look.
- The initial text of `#window` is the `introStatus('15s')` sentence in markup, so it is right without JavaScript.
- The numbered steps: 1. Press **Try it yourself** and watch its tap miss the control it meant. The other two are unchanged.
- The CSS rule `@media (max-height: 760px) { .col-left .steps { display: none; } }` is removed together with its comment. Nothing with `max-height` touches `#window` or `.status`. The 660 px rule that hides the intro stays.
- Script: `updateButtons` sets the text with `agentButtonLabel(taskDone(S.app), S.stepCount, S.lastRunAuto)`. `S.lastRunAuto` is set to true by `runAuto` after its `reset()` and to false by a manual run. The agent button handler calls `agentButtonAction(taskDone(S.app))`; on `'restart'` it calls `reset()` and then `agentStep()`; on `'step'` it calls `agentStep()`. Every place that sets the first-state status uses `introStatus(winLabel())`. The closed-window message and the comments name `Try it yourself`. When the automatic story ends, `runAuto` sets the status with `autoDoneStatus()`.

## The countdown stops when the run is done

`tickCountdown` begins with a check: when `taskDone(S.app)` is true it clears `countdownTimer`, sets `S.countdownUntil = 0`, redraws the timeline and returns, without calling `setStatus`. Otherwise it is unchanged. `reset()` already clears the timer, so a reset or a restart cannot be overwritten by a stale tick. The `core` and `app` blocks and the window logic of a run in progress are not touched.

## Tests

`tests/test_demo_try_it.py` reads `demo/index.html` and checks Requirements 1, 3, 5 and 7 by reading the markup and the style. It checks Requirements 1.3 to 1.5, 2 and 4 by running the labels block in Node. It checks that the `core` and `app` blocks still exist. It fails on the page as it is now.

## Verification

`python acceptance_try.py N`, `pytest`, `python demo/check_app.py`, `python demo/check_port.py`.
