import Foundation

/// The role and actions of one accessibility element.
public struct ElementInfo: Equatable {
    /// The raw accessibility role, for example "AXStaticText".
    public let role: String
    /// Raw action names, for example ["AXPress"].
    public let actions: [String]

    public init(role: String, actions: [String] = []) {
        self.role = role
        self.actions = actions
    }
}

/// Chooses which element of a chain to report: the control the person meant to press.
public enum ElementPicker {
    /// How many ancestors above the element under the click are searched.
    public static let maxAncestors = 6

    public static let interactiveRoles: Set<String> = [
        "AXButton", "AXLink", "AXCell", "AXCheckBox", "AXRadioButton", "AXSwitch",
        "AXTextField", "AXTextArea", "AXSlider", "AXMenuItem", "AXPopUpButton",
    ]

    public static let frameRoles: Set<String> = ["AXWindow", "AXApplication"]

    public static func isInteractive(_ element: ElementInfo) -> Bool {
        if frameRoles.contains(element.role) { return false }
        return element.actions.contains("AXPress") || interactiveRoles.contains(element.role)
    }

    /// `chain[0]` is the element under the click and `chain[i + 1]` is the parent of `chain[i]`.
    public static func chosenIndex(in chain: [ElementInfo]) -> Int {
        guard let first = chain.first else { return 0 }
        if isInteractive(first) { return 0 }
        let last = min(maxAncestors, chain.count - 1)
        guard last >= 1 else { return 0 }
        for i in 1...last where isInteractive(chain[i]) {
            return i
        }
        return 0
    }
}
