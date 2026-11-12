# Implementation Plan: Field Fixes

## Overview

This plan fixes the five things seen in a real run: the ratio of a pair, the pairing window, the recorder address, the demo, and the documentation. Each numbered group is one stage of work and ends when its checks pass. A task is ticked only when its work exists and passes.

## Tasks

- [x] 1. The specification
  - [x] 1.1 Write `requirements.md`, `design.md` and `tasks.md` in `.kiro/specs/field-fixes/`
    - _Requirements: 1.1 to 7.4_

- [x] 2. The ratio and the window
  - [x] 2.1 Add `ratio_x` and `ratio_y` (default `None`) to `Mismatch` in `poltergeist/action_log.py`
    - _Requirements: 1.1, 1.3, 1.4_
  - [x] 2.2 Fill the ratios in `detect_mismatches`, `None` below the 1.0 threshold; leave the scale rule alone
    - _Requirements: 1.2, 1.5_
  - [x] 2.3 Add the ratio sentence to `describe_mismatch` in `poltergeist/activity.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.4 Read `POLTERGEIST_MISMATCH_WINDOW_SECONDS` in `poltergeist/detection.py`, keep the module constant
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.5 Tests for the ratio, the sentence and the window
    - _Requirements: 7.1_

- [x] 3. The hook address, the example hook file and the agent example
  - [x] 3.1 Parse `--url` and `--url=` in `poltergeist/kiro_hook.py`, with the order of precedence
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 3.2 Update `integrations/kiro/hooks/poltergeist.json` with the absolute path and `--url`
    - _Requirements: 4.4_
  - [x] 3.3 Create `integrations/kiro/agents/simdriver.json`
    - _Requirements: 4.5_
  - [x] 3.4 Tests in `tests/test_kiro_hook.py` for `--url` and the example files
    - _Requirements: 7.1, 7.2_

- [x] 4. The demo and its check
  - [x] 4.1 Add the ratio and the sentence to the JavaScript core of `demo/index.html`, and `ratio_x`, `ratio_y` to the JSON on the page
    - _Requirements: 5.1, 5.2_
  - [x] 4.2 Extend `demo/check_port.py` to compare ratios and sentences
    - _Requirements: 5.3_

- [x] 5. Documentation
  - [x] 5.1 Update `README.md`
    - _Requirements: 6.1 to 6.8_
  - [x] 5.2 Update `docs/usage.md`
    - _Requirements: 6.1 to 6.8_
  - [x] 5.3 Tick the tasks of this plan and run the whole test suite
    - _Requirements: 7.3, 7.4_
