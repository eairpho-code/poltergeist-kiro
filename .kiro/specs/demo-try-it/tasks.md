# Implementation Plan: Demo, Try It Yourself

## Overview

Three stages. Stage 1 writes this specification and the tests. Stage 2 changes the page. Stage 3 writes the documentation and ticks the tasks.

## Tasks

- [x] 1. Specification and tests
  - [x] 1.1 Write `requirements.md`, `design.md` and `tasks.md` in `.kiro/specs/demo-try-it/`
    - _Requirements: all_
  - [x] 1.2 Write `tests/test_demo_try_it.py`: reading checks of the page and Node checks of the labels block; they fail on the current page
    - _Requirements: 1, 2, 3, 4, 5, 7_

- [x] 2. The page
  - [x] 2.1 Add the labels block and use it in `updateButtons`, the agent button handler, the first-state status and the end of the automatic story
    - _Requirements: 1.3, 1.4, 1.5, 2, 3.4, 4_
  - [x] 2.2 Change the markup and style: button names and classes, status line text, numbered steps, remove the 760 px rule, remove every old name
    - _Requirements: 1.1, 1.2, 1.6, 3.1, 3.2, 3.3, 5_
  - [x] 2.3 Check: `pytest`, `python demo/check_app.py`, `python demo/check_port.py`
    - _Requirements: 7_

- [x] 2b. A fix found by running the page
  - [x] 2b.1 `tickCountdown` stops and writes nothing to `#window` once `taskDone(S.app)`; add a test at the end of `tests/test_demo_try_it.py`
    - _Requirements: 8_

- [x] 3. Documentation
  - [x] 3.1 Describe the two modes and the two button names in the README section `The demo`, and in `docs/usage.md` if it describes the demo
    - _Requirements: 6_
