# Implementation Plan: Kiro Integration

## Overview

This plan makes Poltergeist usable from Kiro: a recorder command for a Kiro hook, example files, documentation and tests. Each numbered group is one stage of work and ends when its checks pass.

## Tasks

- [ ] 1. The specification
  - [ ] 1.1 Write `requirements.md`, `design.md` and `tasks.md` in `.kiro/specs/kiro-integration/`
    - _Requirements: 1.1 to 8.3_

- [ ] 2. The recorder
  - [ ] 2.1 Create `poltergeist/kiro_hook.py` with `main()`, `gesture_from_event` and `post_agent_click`
    - Tap (`ui_tap`) and swipe (`ui_swipe`) by the end of the lower-cased tool name
    - Numbers only: booleans, strings, `null` and non-finite values are ignored
    - Device points, scale factor 1, `POST /agent-click`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ] 2.2 Never fail, never hang
    - Exit code 0 and no output in every case, request timeout of 2 seconds at most, address from `POLTERGEIST_URL`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1_
  - [ ] 2.3 Tests for the recorder: `tests/test_kiro_hook.py`
    - _Requirements: 8.1, 8.3_

- [ ] 3. The example files and the console script
  - [ ] 3.1 Add the console script `poltergeist-kiro-hook` to `pyproject.toml`
    - _Requirements: 5.2, 5.3_
  - [ ] 3.2 Create `integrations/kiro/hooks/poltergeist.json`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [ ] 3.3 Create `integrations/kiro/mcp.json`
    - _Requirements: 6.5_
  - [ ] 3.4 Create `integrations/kiro/steering/poltergeist.md`
    - _Requirements: 6.6_
  - [ ] 3.5 Tests for the shape of the example files, in `tests/test_kiro_hook.py`
    - _Requirements: 8.2, 8.3_

- [ ] 4. Documentation
  - [ ] 4.1 Add a Kiro section to `README.md`
    - Steps, and what was and was not checked
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ] 4.2 Add a Kiro section to `docs/usage.md`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ] 4.3 Tick the tasks of this plan and run the whole test suite
