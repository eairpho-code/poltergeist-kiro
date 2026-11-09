import CoreGraphics

/// A completed mouse gesture: a click at a point, or a drag between two points.
public enum Gesture: Equatable {
    case click(at: CGPoint, origin: ClickOrigin)
    case drag(from: CGPoint, to: CGPoint, origin: ClickOrigin)
}

/// Turns presses and releases into clicks and drags, keeping one press per sender so that a
/// person and an agent can use the mouse at the same time without disturbing each other.
public struct PressTracker {
    /// The greatest distance between press and release that still counts as a click (inclusive).
    public let maxClickTravel: CGFloat

    private var presses: [Int: CGPoint] = [:]

    public init(maxClickTravel: CGFloat = 8) {
        self.maxClickTravel = maxClickTravel
    }

    /// Remember a press from the given sender.
    public mutating func press(at point: CGPoint, sourcePID: Int) {
        presses[sourcePID] = point
    }

    /// Complete the press of the same sender. Returns nothing when that sender never pressed.
    /// The press is forgotten once released.
    public mutating func release(at point: CGPoint, sourcePID: Int) -> Gesture? {
        guard let start = presses.removeValue(forKey: sourcePID) else { return nil }
        let origin = ClickOrigin(sourcePID: sourcePID)
        if travel(from: start, to: point) <= maxClickTravel {
            return .click(at: start, origin: origin)
        }
        return .drag(from: start, to: point, origin: origin)
    }

    private func travel(from a: CGPoint, to b: CGPoint) -> CGFloat {
        let dx = b.x - a.x
        let dy = b.y - a.y
        return (dx * dx + dy * dy).squareRoot()
    }
}
