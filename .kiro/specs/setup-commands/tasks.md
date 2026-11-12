# Implementation Plan: Setup Commands

## Overview

This plan adds the console script `poltergeist` with `init kiro` and `doctor`. Each numbered group is one stage of work and ends when its checks pass. A task is ticked only when the work exists and passes.

## Tasks

- [x] 1. The specification
  - [x] 1.1 Write `requirements.md`, `design.md` and `tasks.md` in `.kiro/specs/setup-commands/`
    - _Requirements: 1.1 to 11.3_

- [x] 2. `poltergeist init kiro`
  - [x] 2.1 Package data: copy the example files into `poltergeist/kiro_files/` and list them in `pyproject.toml`
    - _Requirements: 4.1, 4.2_
  - [x] 2.2 Create `poltergeist/cli.py` with `main(argv=None) -> int`, argument checks and the console script
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3_
  - [x] 2.3 Write the hook file with the absolute path and `--url`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.4 Write steering and agent files; merge `mcp.json`
    - _Requirements: 4.1, 5.1, 5.2, 5.3, 5.4, 5.5_
  - [x] 2.5 Statuses, `--force`, `--dry-run`, exit codes and next steps
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2_
  - [x] 2.6 Tests in `tests/test_cli_init.py`, including the package data comparison
    - _Requirements: 4.3, 11.1_

- [x] 3. `poltergeist doctor`
  - [x] 3.1 The nine checks in the fixed order, the summary line and the exit code
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_
  - [x] 3.2 External commands with a 5 second timeout; a missing or hung command is a `warn`
    - _Requirements: 10.1, 10.2_
  - [x] 3.3 Tests in `tests/test_cli_doctor.py`
    - _Requirements: 11.1_

- [ ] 4. Documentation
  - [ ] 4.1 Update `README.md` and `docs/usage.md`: the two commands, the manual steps as the alternative, exit codes, `--dry-run`, `--force`, the observer and the permissions
    - _Requirements: 11.2, 11.3_
