# Implementation Plan: Browser Demo

## Overview

One file, `demo/index.html`, built in five stages. Stages 1 and 2 are checked by the provided Node checks. Stages 3 to 5 are checked in a browser by the reviewer.

## Tasks

- [x] 1. The core
  - [x] 1.1 Create `demo/index.html` with the script wrapped in a function and the core between the `// <core>` markers
    - `makeAction`, `detectMismatches`, `detectScaleProblem`, the formatting helpers and the three describe functions
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x]* 1.2 Check: `python demo/check_port.py` (provided)

- [x] 2. The app
  - [x] 2.1 Add the app between the `// <app>` markers: state, elements, hit testing, taps, swipes, policy, `worked`, `screenHtml`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x]* 2.2 Check: `python demo/check_app.py` (provided)

- [x] 3. The page structure and the first screen
  - [x] 3.1 Write the document, the tokens for both themes, the fonts and the layout of the top bar, headline and stage
    - _Requirements: 3.1, 3.2, 3.5, 4.1, 4.2, 4.3, 4.4_
  - [x] 3.2 Draw the phone from device points, with the initial chat list in the markup, and the empty states of all panels, so the page works without JavaScript
    - _Requirements: 3.3_
  - [x] 3.3 Write the sections below the stage: what the agent is told, the pairing rule (timeline and log), how it works, run it, footer; the honesty note
    - _Requirements: 3.1, 3.4, 9.4_

- [x] 4. Behaviour
  - [x] 4.1 Gestures on the phone, the human actions log, `snapshot()`, and the live watcher lines
    - _Requirements: 6.3, 6.4_
  - [x] 4.2 The agent step, the feed, the correction window with its countdown, pairing messages, self-correction and the end of the task
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  - [x] 4.3 The panels: hook text and raw JSON, scale card, timeline, event log, pair lines on the phone
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 4.4 The automatic demo, reset, the window selector and the test hook
    - _Requirements: 5.8, 9.1, 10.1_

- [x] 5. The ghost, the carry, and polish
  - [x] 5.1 The ghost pointer with its click and drag effects
    - _Requirements: 6.1, 6.2_
  - [x] 5.2 Carrying the agent's cursor away, and the agent's reaction
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [x] 5.3 The theme button, the copy buttons, reduced motion, and the responsive layout at 390 px
    - _Requirements: 3.5, 9.2, 9.3_
  - [ ] 5.4 Final check in a browser
    - _Requirements: all_
