# Implementation Plan: Incremental Scale

## Overview

Two stages. Stage 1 is the server, the watcher and the hook. Stage 2 is the demo and the documentation. The tests and the parity check are provided.

## Tasks

- [ ] 1. The server, the watcher and the hook
  - [ ] 1.1 `get_human_actions` computes the scale problem from the whole log
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [ ] 1.2 Add `scale_changed` to `poltergeist/activity.py`
    - _Requirements: 2.1_
  - [ ] 1.3 The watcher reports a scale problem once, and again when it changes
    - _Requirements: 2.2, 2.3, 2.5, 2.6_
  - [ ] 1.4 `CursorStore.load_scale` and `save_scale`, and the hook's use of them
    - _Requirements: 2.4, 2.5, 3.1, 3.2_
  - [ ]* 1.5 Tests: `tests/test_incremental_scale.py` (provided)

- [ ] 2. The demo and the documentation
  - [ ] 2.1 Add `scaleChanged` to the core of `demo/index.html` and use it in `hearStep`
    - _Requirements: 4.1, 4.2_
  - [ ]* 2.2 Check: `python demo/check_port.py` (provided)
  - [ ] 2.3 Update `docs/usage.md`
    - _Requirements: 5.1_
