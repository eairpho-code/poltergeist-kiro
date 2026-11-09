import Foundation

/// The accessibility element under a click: a short role and, optionally, a short label.
public struct UIElementPayload: Codable, Equatable {
    public let role: String
    public let label: String?

    public init(role: String, label: String? = nil) {
        self.role = role
        self.label = label
    }

    private enum CodingKeys: String, CodingKey {
        case role
        case label
    }
}

/// The JSON body the server expects for a click or a drag, in device points.
public struct ClickPayload: Codable, Equatable {
    public let x: Double
    public let y: Double
    public let coordinateSpace: String
    public let scaleFactor: Double
    public let uiElement: UIElementPayload?
    public let endX: Double?
    public let endY: Double?

    private enum CodingKeys: String, CodingKey {
        case x
        case y
        case coordinateSpace = "coordinate_space"
        case scaleFactor = "scale_factor"
        case uiElement = "ui_element"
        case endX = "end_x"
        case endY = "end_y"
    }

    /// A click at a device point.
    public init(devicePointX x: Double, y: Double, uiElement: UIElementPayload? = nil) {
        self.x = ClickPayload.round2(x)
        self.y = ClickPayload.round2(y)
        self.coordinateSpace = "device_points"
        self.scaleFactor = 1.0
        self.uiElement = uiElement
        self.endX = nil
        self.endY = nil
    }

    /// A drag from a device point to an end device point.
    public init(devicePointX x: Double, y: Double, endX: Double, endY: Double, uiElement: UIElementPayload? = nil) {
        self.x = ClickPayload.round2(x)
        self.y = ClickPayload.round2(y)
        self.coordinateSpace = "device_points"
        self.scaleFactor = 1.0
        self.uiElement = uiElement
        self.endX = ClickPayload.round2(endX)
        self.endY = ClickPayload.round2(endY)
    }

    /// Encode to JSON data, omitting absent optional keys.
    public func jsonData() throws -> Data {
        try JSONEncoder().encode(self)
    }

    private static func round2(_ value: Double) -> Double {
        (value * 100).rounded() / 100
    }
}

/// Short, safe labels for the server.
public enum Labels {
    /// Trim whitespace, drop empty text, and cut to 50 characters (counting characters, not bytes).
    public static func short(_ text: String?) -> String? {
        guard let text = text else { return nil }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        if trimmed.count > 50 {
            return String(trimmed.prefix(50))
        }
        return trimmed
    }
}

/// Maps accessibility roles to the short role names the server uses.
public enum RoleNames {
    private static let known: [String: String] = [
        "AXButton": "button",
        "AXTextField": "text_field",
        "AXTextArea": "text_area",
        "AXStaticText": "text",
        "AXSwitch": "switch",
        "AXSlider": "slider",
        "AXCheckBox": "checkbox",
        "AXImage": "image",
        "AXLink": "link",
        "AXMenuItem": "menu_item"
    ]

    /// Map an accessibility role to the server's short role. Known roles get a fixed name;
    /// any other role becomes lower snake case without the `AX` prefix, and `unknown` when empty.
    public static func name(forAXRole role: String) -> String {
        if let mapped = known[role] {
            return mapped
        }
        let stripped = role.hasPrefix("AX") ? String(role.dropFirst(2)) : role
        let snake = snakeCase(stripped)
        return snake.isEmpty ? "unknown" : snake
    }

    /// Turn a camel/Pascal case identifier into lower snake case.
    private static func snakeCase(_ text: String) -> String {
        var result = ""
        for char in text {
            if char.isUppercase {
                if !result.isEmpty {
                    result.append("_")
                }
                result.append(Character(char.lowercased()))
            } else {
                result.append(char)
            }
        }
        return result
    }
}
