import ApplicationServices
import AppKit
import Foundation
import ObserverCore

/// Looks up the iOS Simulator's device displays and the element under a click through the
/// accessibility API, and runs `xcrun simctl` to learn the device sizes.
final class SimulatorScreens {
    /// The Simulator's bundle identifier.
    static let simulatorBundleID = "com.apple.iphonesimulator"

    private let systemWide = AXUIElementCreateSystemWide()

    /// The `SimulatorScreen` of each window of the running Simulator app. Returns an empty array
    /// when the Simulator is not running or none of its windows show a device.
    func current() -> [SimulatorScreen] {
        guard let app = runningSimulator() else { return [] }

        let appElement = AXUIElementCreateApplication(app.processIdentifier)
        guard let windows = axArray(appElement, kAXWindowsAttribute as CFString) else { return [] }

        let booted = (try? bootedDevices()) ?? []
        let bundlePaths = (try? deviceTypeBundlePaths()) ?? [:]
        var profileCache: [String: ProfileScreen] = [:]

        var screens: [SimulatorScreen] = []
        for window in windows {
            guard let rect = largestGroupRect(in: window) else { continue }
            guard
                let title = axString(window, kAXTitleAttribute as CFString),
                let name = SimctlParsing.deviceName(fromWindowTitle: title),
                let device = booted.first(where: { $0.name == name })
            else { continue }

            let profile: ProfileScreen
            if let cached = profileCache[device.deviceTypeIdentifier] {
                profile = cached
            } else if let resolved = profileScreen(
                for: device.deviceTypeIdentifier, bundlePaths: bundlePaths
            ) {
                profileCache[device.deviceTypeIdentifier] = resolved
                profile = resolved
            } else {
                continue
            }

            let deviceProfile = DeviceProfile(
                name: name,
                pixelWidth: profile.pixelWidth,
                pixelHeight: profile.pixelHeight,
                scale: profile.scale
            )
            screens.append(SimulatorScreen(rect: rect, device: deviceProfile))
        }
        return screens
    }

    /// The bundle identifier of the application under a global point, through the accessibility
    /// element at that position. Returns nothing when nothing is there.
    func topApplication(atGlobal point: CGPoint) -> String? {
        guard let element = elementAtPosition(point) else { return nil }
        var pid: pid_t = 0
        guard AXUIElementGetPid(element, &pid) == .success else { return nil }
        return NSRunningApplication(processIdentifier: pid)?.bundleIdentifier
    }

    /// Whether the Simulator is the top application at a global point.
    func simulatorIsOnTop(atGlobal point: CGPoint) -> Bool {
        topApplication(atGlobal: point) == Self.simulatorBundleID
    }

    /// The element under a global point as a `UIElementPayload`: its short role, and its short
    /// label only when asked. Returns nothing when there is no element.
    func element(atGlobal point: CGPoint, includeLabel: Bool) -> UIElementPayload? {
        guard let element = elementAtPosition(point) else { return nil }
        let role = axString(element, kAXRoleAttribute as CFString) ?? ""
        let shortRole = RoleNames.name(forAXRole: role)
        guard includeLabel else {
            return UIElementPayload(role: shortRole, label: nil)
        }
        let rawLabel = axString(element, kAXTitleAttribute as CFString)
            ?? axString(element, kAXDescriptionAttribute as CFString)
            ?? axString(element, kAXValueAttribute as CFString)
        return UIElementPayload(role: shortRole, label: Labels.short(rawLabel))
    }

    // MARK: - Accessibility helpers

    private func runningSimulator() -> NSRunningApplication? {
        NSRunningApplication.runningApplications(withBundleIdentifier: Self.simulatorBundleID).first
    }

    private func elementAtPosition(_ point: CGPoint) -> AXUIElement? {
        var element: AXUIElement?
        let result = AXUIElementCopyElementAtPosition(
            systemWide, Float(point.x), Float(point.y), &element
        )
        return result == .success ? element : nil
    }

    /// The frame of the largest `AXGroup` inside a window, which is the device display.
    private func largestGroupRect(in window: AXUIElement) -> CGRect? {
        var best: CGRect?
        for group in groups(in: window) {
            guard let frame = axFrame(group) else { continue }
            if best == nil || frame.width * frame.height > best!.width * best!.height {
                best = frame
            }
        }
        return best
    }

    /// All `AXGroup` descendants of an element (searching children recursively).
    private func groups(in element: AXUIElement, depth: Int = 0) -> [AXUIElement] {
        guard depth < 8 else { return [] }
        guard let children = axArray(element, kAXChildrenAttribute as CFString) else { return [] }
        var found: [AXUIElement] = []
        for child in children {
            if axString(child, kAXRoleAttribute as CFString) == (kAXGroupRole as String) {
                found.append(child)
            }
            found.append(contentsOf: groups(in: child, depth: depth + 1))
        }
        return found
    }

    private func axArray(_ element: AXUIElement, _ attribute: CFString) -> [AXUIElement]? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, attribute, &value) == .success else { return nil }
        return value as? [AXUIElement]
    }

    private func axString(_ element: AXUIElement, _ attribute: CFString) -> String? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, attribute, &value) == .success else { return nil }
        return value as? String
    }

    private func axFrame(_ element: AXUIElement) -> CGRect? {
        guard
            let origin = axPoint(element, kAXPositionAttribute as CFString),
            let size = axSize(element, kAXSizeAttribute as CFString)
        else { return nil }
        return CGRect(origin: origin, size: size)
    }

    private func axPoint(_ element: AXUIElement, _ attribute: CFString) -> CGPoint? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, attribute, &value) == .success else { return nil }
        let axValue = value as! AXValue
        var point = CGPoint.zero
        guard AXValueGetValue(axValue, .cgPoint, &point) else { return nil }
        return point
    }

    private func axSize(_ element: AXUIElement, _ attribute: CFString) -> CGSize? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, attribute, &value) == .success else { return nil }
        let axValue = value as! AXValue
        var size = CGSize.zero
        guard AXValueGetValue(axValue, .cgSize, &size) else { return nil }
        return size
    }

    // MARK: - simctl

    private func bootedDevices() throws -> [BootedDevice] {
        let data = try runProcess(["simctl", "list", "devices", "booted", "-j"])
        return try SimctlParsing.bootedDevices(fromDevicesJSON: data)
    }

    private func deviceTypeBundlePaths() throws -> [String: String] {
        let data = try runProcess(["simctl", "list", "devicetypes", "-j"])
        return try SimctlParsing.deviceTypeBundlePaths(fromDeviceTypesJSON: data)
    }

    private func profileScreen(
        for deviceTypeIdentifier: String, bundlePaths: [String: String]
    ) -> ProfileScreen? {
        guard let bundlePath = bundlePaths[deviceTypeIdentifier] else { return nil }
        let plistPath = (bundlePath as NSString)
            .appendingPathComponent("Contents/Resources/profile.plist")
        guard let data = FileManager.default.contents(atPath: plistPath) else { return nil }
        return try? SimctlParsing.screen(fromProfilePlist: data)
    }

    /// Run `xcrun` with the given arguments and return its standard output.
    private func runProcess(_ arguments: [String]) throws -> Data {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/xcrun")
        process.arguments = arguments
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        try process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return data
    }
}
