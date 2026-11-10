# Implementation Plan: Interactive Element

## Overview

Three stages: the pure function, the executable that uses it, and the sentences with the demo and the documentation. The tests are provided.

## Tasks

- [x] 1. The pure function
  - [x] 1.1 Create `ElementPicker.swift` with `ElementInfo` and `ElementPicker`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x]* 1.2 Unit tests: `ElementPickerTests` (provided)

- [x] 2. Use it in the observer
  - [x] 2.1 Walk up from the element under the click and report the chosen element in `SimulatorScreens.swift`
    - _Requirements: 2.1, 2.2, 2.3_

- [ ] 3. The sentences, the demo and the documentation
  - [x] 3.1 Name the element in `describe_action` as the requirements say
    - _Requirements: 3.1, 3.2_
  - [x]* 3.2 Tests: `tests/test_element_wording.py` (provided)
  - [ ] 3.3 Make `describeAction` in the demo produce the same sentences
    - _Requirements: 3.3_
  - [ ]* 3.4 Check: `python demo/check_port.py` (provided)
  - [ ] 3.5 Update `docs/usage.md` and `README.md`
    - _Requirements: 4.1_
