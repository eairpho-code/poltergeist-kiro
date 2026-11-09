# Design Document

## Overview

A Swift package in `observer/` with two targets, as defined in `observer/Package.swift`:

- `ObserverCore`, a library with pure logic and no system access. It is fully covered by unit tests in `observer/Tests/ObserverCoreTests`.
- `poltergeist-observer`, an executable target that talks to macOS and to the server. It has no unit tests and is checked by building it, by its command line behaviour and by a live run.

```
 mouse ──▶ ClickTap ──▶ PressTracker ──▶ gesture(origin)
                                              │
              ClickPolicy ◀── sender names ───┤
                    │ actor                   │
                    ▼                         ▼
        SimulatorScreens ── display, top app, element ──▶ ClickPayload ──▶ ServerClient
```

The package targets macOS 13 and Swift 5.9 and uses only system frameworks.

## ObserverCore

One file per topic, public types only where the tests need them.

- `SimulatorScreen.swift`: `DeviceProfile`, `SimulatorScreen` (`displayedPointSize`, `devicePoint(forGlobal:)`, `devicePointClamped(forGlobal:)`) and `ScreenLookup` (`screen(containing:in:edgeTolerance:)`, `edgeTolerance`).
- `SimctlParsing.swift`: `BootedDevice`, `ProfileScreen`, `SimctlParsingError`, and the functions of Requirement 2. It parses data it is given and never runs a process.
- `ClickPayload.swift`: `UIElementPayload`, `ClickPayload` (a `Codable` struct with snake case keys and two initializers, one for a click and one for a drag), `Labels` and `RoleNames`.
- `ClickOrigin.swift`: `ClickOrigin`, `ClickActor` and `ClickPolicy` with `actor(for:senderNames:)`.
- `PressTracker.swift`: `PressTracker` with `press(at:sourcePID:)`, `release(at:sourcePID:)` and the `Gesture` enum.

## Executable

- `Options.swift`: a struct with the defaults and a static `parse(_:)` that throws `ParseError` (`help` or `invalid(message)`). It holds the usage text.
- `ServerClient.swift`: a class that posts a `ClickPayload` with `URLSession` (ephemeral configuration, 3 second request timeout) and reports the status code and body, or the error, to a completion handler.
- `ClickTap.swift`: a class that creates a listen-only `CGEvent` tap on `cgSessionEventTap` for left mouse down and up, feeds a `PressTracker` and calls an `onClick` or an `onDrag` closure with the origin. `start()` returns false when macOS refuses the tap. A tap that macOS disabled is enabled again.
- `SimulatorScreens.swift`: a class that uses the accessibility API.
  - `current()` returns the `SimulatorScreen` of each window of the running Simulator app (bundle identifier `com.apple.iphonesimulator`). The display is the largest `AXGroup` inside the window. The device comes from the window title (`SimctlParsing.deviceName`) matched with the booted devices of `xcrun simctl list devices booted -j`, and the screen size from the `profile.plist` found through `xcrun simctl list devicetypes -j`. Process output is parsed by `SimctlParsing`.
  - `topApplication(atGlobal:)` and `simulatorIsOnTop(atGlobal:)` use the accessibility element at a screen position (system-wide element) to find the application that really is under the pointer.
  - `element(atGlobal:includeLabel:)` returns a `UIElementPayload` with the short role of the element under the point and, only when asked, its short label.
- `main.swift`: parse the options (help exits 0, an error exits 2), check that the process is trusted for accessibility (exit 1 with an explanation otherwise), build the objects, start the tap (exit 1 with an explanation when refused), install SIGINT and SIGTERM handlers that exit 0, log that it is watching, and run the run loop. Each gesture is handled on a serial queue, away from the event tap, so a slow lookup cannot stall the mouse. A gesture is dropped, with a reason in `--verbose` mode, when its actor is none, when it does not start on a display, or when the Simulator is not on top. In dry-run mode it prints the payload instead of posting it.

## Error handling

- A server that cannot be reached or refuses a gesture is logged and the observer keeps running.
- Accessibility lookups that fail return nothing, and the gesture is reported without an element.

## Testing

- `swift test` runs the 54 unit tests of `ObserverCore`.
- `swift build -c release` must succeed without errors.
- The executable is run with `--help`, with a bad option, with `--dry-run`, and against a booted Simulator.
