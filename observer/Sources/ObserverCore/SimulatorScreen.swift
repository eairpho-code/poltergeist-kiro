import CoreGraphics

/// A simulated device: its name, native pixel size and backing scale.
public struct DeviceProfile: Equatable {
    public let name: String
    public let pixelWidth: CGFloat
    public let pixelHeight: CGFloat
    public let scale: CGFloat

    public init(name: String, pixelWidth: CGFloat, pixelHeight: CGFloat, scale: CGFloat) {
        self.name = name
        self.pixelWidth = pixelWidth
        self.pixelHeight = pixelHeight
        self.scale = scale
    }

    /// The device size in points, in portrait orientation (pixels divided by scale).
    public var pointSize: CGSize {
        CGSize(width: pixelWidth / scale, height: pixelHeight / scale)
    }
}

/// The rectangle inside a Simulator window that shows a device screen, and the device it shows.
public struct SimulatorScreen: Equatable {
    /// The display rectangle in global Mac points.
    public let rect: CGRect
    public let device: DeviceProfile

    public init(rect: CGRect, device: DeviceProfile) {
        self.rect = rect
        self.device = device
    }

    /// The device size in points as currently displayed. When the display is shown rotated
    /// (wider than tall while the device is portrait, or vice versa) width and height are swapped.
    public var displayedPointSize: CGSize {
        let portrait = device.pointSize
        let landscape = CGSize(width: portrait.height, height: portrait.width)
        let displayIsLandscape = rect.width > rect.height
        let deviceIsLandscape = portrait.width > portrait.height
        return displayIsLandscape == deviceIsLandscape ? portrait : landscape
    }

    /// Map a global Mac point to a device point. Returns nothing when the point is outside the
    /// rectangle or the rectangle is empty. The result is scaled by the displayed size, so a
    /// zoomed window still gives correct device coordinates.
    public func devicePoint(forGlobal global: CGPoint) -> CGPoint? {
        guard !rect.isEmpty, rect.contains(global) else { return nil }
        return scaled(global)
    }

    /// Like `devicePoint(forGlobal:)` but moves a point outside the rectangle to its nearest edge
    /// first, so a drag that leaves the display ends on its edge. Returns nothing for an empty rect.
    public func devicePointClamped(forGlobal global: CGPoint) -> CGPoint? {
        guard !rect.isEmpty else { return nil }
        let clamped = CGPoint(
            x: min(max(global.x, rect.minX), rect.maxX),
            y: min(max(global.y, rect.minY), rect.maxY)
        )
        return scaled(clamped)
    }

    private func scaled(_ global: CGPoint) -> CGPoint {
        let size = displayedPointSize
        let fx = (global.x - rect.minX) / rect.width
        let fy = (global.y - rect.minY) / rect.height
        return CGPoint(x: fx * size.width, y: fy * size.height)
    }
}

/// Finds which display a point falls on.
public enum ScreenLookup {
    /// A small tolerance so gestures that start at the very edge of a display still count.
    public static let edgeTolerance: CGFloat = 2

    /// Return the first screen whose rectangle contains the point, allowing the given tolerance
    /// around each rectangle. The default tolerance is 0.
    public static func screen(
        containing point: CGPoint,
        in screens: [SimulatorScreen],
        edgeTolerance: CGFloat = 0
    ) -> SimulatorScreen? {
        screens.first { screen in
            let r = screen.rect.insetBy(dx: -edgeTolerance, dy: -edgeTolerance)
            return !screen.rect.isEmpty && r.contains(point)
        }
    }
}
