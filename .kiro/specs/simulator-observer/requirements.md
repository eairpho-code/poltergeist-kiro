# Requirements Document

## Introduction

The Poltergeist server needs to know which clicks happen in the iOS Simulator and who made them. This feature is a small macOS command line program, `poltergeist-observer`. It watches the Mac's mouse, finds out where the Simulator shows a device display, converts a click on the Mac screen into device points, decides whether a person or an AI agent made the click, and reports it to the server as `POST /human-click` or `POST /agent-click`.

The observer only sees the mouse. It never changes or blocks an event, and it ignores everything outside a Simulator display.

## Glossary

- **Device points**: the coordinates of a simulated device, such as 430 x 932 for an iPhone 14 Pro Max, with the origin at the top left.
- **Global point**: a position on the Mac screen, in points, with the origin at the top left of the main display.
- **Display**: the rectangle inside a Simulator window that shows the device screen.
- **Click**: a press and release that stay close together. **Drag**: a press and release that are far apart, such as a swipe.
- **Hardware click**: a click from real mouse hardware. **Synthetic click**: a click that a program posted, such as an AI agent that moves the real mouse.
- **Sender**: the process that created a mouse event.

## Requirements

### Requirement 1: Map a Mac point to a device point

**User Story:** As the observer, I want to turn a position on the Mac screen into device points, so that the server receives coordinates the agent understands.

#### Acceptance Criteria

1. A `DeviceProfile` SHALL hold a name, pixel width, pixel height and scale, and report its size in points in portrait orientation (pixels divided by scale).
2. A `SimulatorScreen` SHALL hold the display rectangle in global points and a `DeviceProfile`.
3. THE displayed size in points SHALL follow the shape of the rectangle: when the display is shown rotated, width and height are swapped.
4. WHEN a global point is inside the rectangle, `devicePoint(forGlobal:)` SHALL return the device point, scaled by the displayed size so that a zoomed window still gives correct results. Outside the rectangle, or for an empty rectangle, it SHALL return nothing.
5. `devicePointClamped(forGlobal:)` SHALL do the same but move a point that lies outside the rectangle to the nearest edge first, so that a drag that leaves the display ends on its edge.
6. `ScreenLookup.screen(containing:in:edgeTolerance:)` SHALL return the first display that contains the point, allowing the given tolerance around each display. The default tolerance is 0 and `ScreenLookup.edgeTolerance` is 2 points, so gestures that start at the very edge still count.

### Requirement 2: Understand what simctl prints

**User Story:** As the observer, I want to learn which devices are booted and how big their screens are, so that I can build the device profile of a display.

#### Acceptance Criteria

1. `SimctlParsing.bootedDevices(fromDevicesJSON:)` SHALL return the devices whose state is `Booted` from the JSON of `xcrun simctl list devices booted -j`, as name, udid and device type identifier, sorted by udid. Entries that miss a field SHALL be skipped. JSON of the wrong shape SHALL throw `SimctlParsingError.malformed`.
2. `deviceTypeBundlePaths(fromDeviceTypesJSON:)` SHALL return a dictionary from device type identifier to bundle path, from the JSON of `xcrun simctl list devicetypes -j`.
3. `screen(fromProfilePlist:)` SHALL read `mainScreenWidth`, `mainScreenHeight` and `mainScreenScale` from a device type's `profile.plist` and throw `malformed` unless all three are present and greater than zero.
4. `deviceName(fromWindowTitle:)` SHALL return the device name in a Simulator window title such as `iPhone 14 Pro Max – iOS 26.5`, accepting an en dash or a hyphen with spaces around it as the separator, and nothing when there is no separator or the name is empty.

### Requirement 3: Build the request body

**User Story:** As the observer, I want to produce exactly the JSON the server expects.

#### Acceptance Criteria

1. A `ClickPayload` SHALL encode to JSON with the keys `x`, `y`, `coordinate_space`, `scale_factor`, `ui_element` (optional) and, for a drag, `end_x` and `end_y`.
2. A payload built from device points SHALL use `device_points` and a scale factor of 1.0, and SHALL round every coordinate to two decimals.
3. A payload built with an end point SHALL be a drag; one built without SHALL have no end point.
4. `Labels.short` SHALL trim whitespace, return nothing for an empty text or `nil`, and cut a label to 50 characters.
5. `RoleNames.name(forAXRole:)` SHALL map accessibility roles to the short roles of the server (for example `AXButton` to `button`, `AXTextField` to `text_field`, `AXSwitch` to `switch`) and turn any other role into lower snake case without the `AX` prefix (`AXMenuItem` to `menu_item`), with `unknown` for an empty role.

### Requirement 4: Decide who clicked

**User Story:** As someone running an AI agent that moves the real mouse, I want its clicks to be reported as the agent's, so that only my clicks come back as human actions.

#### Acceptance Criteria

1. A click whose sender process id is 0 SHALL have origin `hardware`. Any other sender id SHALL give origin `synthetic` with that id.
2. A hardware click SHALL be attributed to the human.
3. A synthetic click SHALL be attributed to the agent when one of the sender's names (process name, app name or bundle identifier) equals one of the configured agent apps, ignoring case.
4. Any other synthetic click SHALL be ignored, unless the policy counts synthetic clicks as the human's, in which case it SHALL be attributed to the human.

### Requirement 5: Tell clicks from drags

**User Story:** As the observer, I want to turn presses and releases into clicks and drags, even when a person and an agent use the mouse at the same time.

#### Acceptance Criteria

1. A `PressTracker` SHALL remember each press per sender, and a release SHALL complete the press of the same sender, not the latest press of anyone.
2. WHEN the release is within 8 points of the press (the default `maxClickTravel`), THE tracker SHALL report a click at the press position; otherwise a drag from the press position to the release position. Each gesture SHALL carry the origin of its sender.
3. A release from a sender that never pressed SHALL report nothing, and a press SHALL be forgotten once released.

### Requirement 6: Command line

**User Story:** As a user, I want a few clear options.

#### Acceptance Criteria

1. THE program SHALL accept `--server URL` (http or https with a host, default `http://127.0.0.1:8000`), `--send-labels`, `--agent-app NAME` (repeatable), `--include-synthetic`, `--dry-run`, `--verbose` and `-h`/`--help`.
2. `--help` SHALL print the usage text and exit with code 0. A bad option or a missing value SHALL print the reason and the usage text and exit with code 2.
3. THE usage text SHALL explain each option and that the Accessibility and Input Monitoring permissions are needed.

### Requirement 7: Watch the mouse

**User Story:** As the observer, I want to see every mouse press and release without interfering.

#### Acceptance Criteria

1. THE program SHALL use a listen-only event tap on the session for left mouse down and up. It SHALL never change or block an event, SHALL switch the tap back on when macOS disables it, and SHALL read the sender's process id from each event.
2. IF macOS refuses the tap, THEN the program SHALL explain that Input Monitoring is missing and exit with code 1. IF Accessibility is not granted, it SHALL explain that and exit with code 1.

### Requirement 8: Find the Simulator display and the element under a click

**User Story:** As the observer, I want to know which display a click is on and what it hit.

#### Acceptance Criteria

1. THE program SHALL find the displays of the running Simulator windows through the accessibility API, take the largest group inside each window as the display, resolve the device from the window title and `simctl`, and build a `SimulatorScreen` for each.
2. A click SHALL be reported only when its start is on a display (with the edge tolerance) and the Simulator is the top application at that point. Otherwise it SHALL be ignored.
3. THE program SHALL read the role of the accessibility element under the click, and its short label only when `--send-labels` is given.
4. A drag SHALL be located by its start point. Its end point SHALL be clamped to the display.

### Requirement 9: Report to the server

**User Story:** As the Poltergeist server, I want each gesture as one HTTP request.

#### Acceptance Criteria

1. A human gesture SHALL be posted to `/human-click` and an agent gesture to `/agent-click` of the configured server, with `Content-Type: application/json` and a 3 second timeout.
2. WITH `--dry-run`, THE program SHALL print `<human|agent> <click|drag> <json>` to standard output for each gesture and SHALL NOT contact the server.
3. THE program SHALL log to standard error: a line when it starts, a line for each reported gesture, a line when the server answers with an error status or cannot be reached. WITH `--verbose` it SHALL also say why a gesture was ignored.
4. THE program SHALL exit with code 0 on SIGINT or SIGTERM.

### Requirement 10: Privacy

#### Acceptance Criteria

1. Labels SHALL NOT be sent unless `--send-labels` is given.
2. Clicks outside a Simulator display SHALL NOT be reported or logged, except as a position in `--verbose` mode, which the usage text says is for debugging only.
