# Design Document

## Overview

A pure function in `ObserverCore` picks the element from a chain of roles and actions. The executable builds the chain with the accessibility API and calls it. `activity.py` and the demo name the element in a way that a bare text is not called "a text".

## Components

### `observer/Sources/ObserverCore/ElementPicker.swift`

```swift
public struct ElementInfo: Equatable {
    public let role: String        // the raw accessibility role, for example "AXStaticText"
    public let actions: [String]   // raw action names, for example ["AXPress"]
    public init(role: String, actions: [String] = [])
}

public enum ElementPicker {
    public static let maxAncestors = 6
    public static let interactiveRoles: Set<String>   // the roles of the glossary
    public static let frameRoles: Set<String>         // ["AXWindow", "AXApplication"]
    public static func isInteractive(_ element: ElementInfo) -> Bool
    public static func chosenIndex(in chain: [ElementInfo]) -> Int
}
```

`chain[0]` is the element under the click and `chain[i + 1]` is the parent of `chain[i]`.

- `isInteractive`: false for a frame role. Otherwise true when `actions` contains `"AXPress"` or the role is in `interactiveRoles`.
- `chosenIndex`: an empty chain gives `0`. If `chain[0]` is interactive, `0`. Otherwise the first index `i` in `1...min(maxAncestors, chain.count - 1)` with `isInteractive(chain[i])`. Otherwise `0`.

### `observer/Sources/poltergeist-observer/SimulatorScreens.swift`

`element(atGlobal:includeLabel:)` keeps its signature. It gets the element under the point, walks `kAXParentAttribute` up to `ElementPicker.maxAncestors` times collecting `ElementInfo` (role with `kAXRoleAttribute`, action names with `AXUIElementCopyActionNames`), asks `ElementPicker.chosenIndex(in:)` and reports the role (through `RoleNames`) and, only when `includeLabel`, the short label of the chosen element. Any error while walking up ends the walk.

### `poltergeist/activity.py` and `demo/index.html`

`describe_action` and `describeAction` build the element phrase from `role` and `label` as in Requirement 3.1. The demo's actions carry `role` and `label`.

## Testing

`observer/Tests/ObserverCoreTests/ElementPickerTests.swift` tests the pure function. `tests/test_element_wording.py` tests the sentences. `demo/check_port.py` compares the sentences of the demo with the Python ones. The accessibility calls cannot be unit tested; the stage's check builds the executable and checks that it uses `ElementPicker`.
