# Implementation Plan: Agent Awareness

## Overview

This plan extends the Human Action Log so that an agent notices what a person does while it works. Each numbered group is one stage of work and ends when its tests pass.

## Tasks

- [ ] 1. Record drags
  - [ ] 1.1 Extend ClickAction and ActionLog
    - Add `kind`, `end_x`, `end_y` to `ClickAction`
    - Add `record_human_drag` and `record_agent_drag`, normalizing the end point with the start point's scale factor
    - Reject a non-finite end point with `end_x and end_y must be finite`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [ ] 1.2 Make mismatch detection pair clicks only
    - _Requirements: 2.1, 2.2_
  - [ ] 1.3 Include `kind`, `end_x`, `end_y` in the `get_human_actions` tool result
    - _Requirements: 1.7_
  - [ ] 1.4 Accept drags on `POST /human-click`
    - Optional `end_x` and `end_y`, both or neither, and `kind` in the response
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ]* 1.5 Tests for drags: `tests/test_drags.py` (provided)

- [ ] 2. Agent clicks over HTTP
  - [ ] 2.1 Share the request handling between `/human-click` and the new `POST /agent-click`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [ ] 2.2 Log each recorded agent click and keep agent clicks out of the human actions
    - _Requirements: 4.5, 4.6_
  - [ ]* 2.3 Tests for the endpoint: `tests/test_agent_endpoint.py` (provided)

- [ ] 3. Read and describe the human's actions
  - [ ] 3.1 Add `ActionLog.now()` and a public `parse_timestamp`
    - _Requirements: 5.1_
  - [ ] 3.2 Add `GET /human-actions` with `since` and `server_time`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ] 3.3 Create `poltergeist/activity.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 4. Watcher and hook
  - [ ] 4.1 Create `poltergeist/watch.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [ ] 4.2 Create `poltergeist/claude_hook.py`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_
  - [ ]* 4.3 Tests for the read route, descriptions, watcher and hook: `tests/test_awareness.py` (provided)

- [ ] 5. Checkpoint - Everything passes
  - Run all tests and ask the user if questions arise.

- [ ] 6. Install and document
  - [ ] 6.1 Define the commands `poltergeist-server`, `poltergeist-watch` and `poltergeist-claude-hook` in `pyproject.toml`
    - _Requirements: 9.1_
  - [ ] 6.2 Write the README
    - _Requirements: 9.2_
  - [ ] 6.3 Write `docs/usage.md` with every route, tool and environment variable
    - _Requirements: 9.3_
