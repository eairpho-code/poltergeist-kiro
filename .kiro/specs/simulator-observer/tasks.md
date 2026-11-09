# Implementation Plan: Simulator Observer

## Overview

Each numbered group is one stage of work and ends when its checks pass. The package manifest and the unit tests are provided.

## Tasks

- [ ] 1. Map points and parse simctl output
  - [ ] 1.1 Create `SimulatorScreen.swift` with `DeviceProfile`, `SimulatorScreen` and `ScreenLookup`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [ ] 1.2 Create `SimctlParsing.swift`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [ ]* 1.3 Unit tests: `SimulatorScreenTests` and `SimctlParsingTests` (provided)

- [ ] 2. Request bodies, who clicked, and clicks versus drags
  - [ ] 2.1 Create `ClickPayload.swift` with `ClickPayload`, `UIElementPayload`, `Labels` and `RoleNames`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ] 2.2 Create `ClickOrigin.swift` with `ClickOrigin`, `ClickActor` and `ClickPolicy`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [ ] 2.3 Create `PressTracker.swift`
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ]* 2.4 Unit tests: `ClickPayloadTests`, `ClickOriginTests` and `PressTrackerTests` (provided)

- [ ] 3. Checkpoint - The core is complete
  - Run `swift test` and ask the user if questions arise.

- [ ] 4. The executable
  - [ ] 4.1 Create `Options.swift`
    - _Requirements: 6.1, 6.2, 6.3_
  - [ ] 4.2 Create `ServerClient.swift`
    - _Requirements: 9.1_
  - [ ] 4.3 Create `ClickTap.swift`
    - _Requirements: 7.1, 7.2_
  - [ ] 4.4 Create `SimulatorScreens.swift`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 10.2_
  - [ ] 4.5 Create `main.swift`
    - _Requirements: 6.2, 7.2, 8.2, 8.4, 9.2, 9.3, 9.4, 10.1_

- [ ] 5. Final checkpoint - The observer builds and runs
  - `swift build -c release` succeeds, `--help` exits 0, a bad option exits 2, and a dry run starts and stops cleanly.
