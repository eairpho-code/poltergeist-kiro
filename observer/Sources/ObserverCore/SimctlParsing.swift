import Foundation

/// A simulated device that is currently booted.
public struct BootedDevice: Equatable {
    public let name: String
    public let udid: String
    public let deviceTypeIdentifier: String

    public init(name: String, udid: String, deviceTypeIdentifier: String) {
        self.name = name
        self.udid = udid
        self.deviceTypeIdentifier = deviceTypeIdentifier
    }
}

/// The screen size read from a device type's `profile.plist`.
public struct ProfileScreen: Equatable {
    public let pixelWidth: CGFloat
    public let pixelHeight: CGFloat
    public let scale: CGFloat

    public init(pixelWidth: CGFloat, pixelHeight: CGFloat, scale: CGFloat) {
        self.pixelWidth = pixelWidth
        self.pixelHeight = pixelHeight
        self.scale = scale
    }
}

public enum SimctlParsingError: Error {
    case malformed
}

/// Parses the output of `xcrun simctl` and Simulator window titles. Never runs a process.
public enum SimctlParsing {
    /// Return the booted devices from the JSON of `xcrun simctl list devices booted -j`, as name,
    /// udid and device type identifier, sorted by udid. Entries missing a field are skipped.
    /// JSON of the wrong shape throws `.malformed`.
    public static func bootedDevices(fromDevicesJSON data: Data) throws -> [BootedDevice] {
        guard
            let top = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let devices = top["devices"] as? [String: Any]
        else {
            throw SimctlParsingError.malformed
        }

        var result: [BootedDevice] = []
        for (_, value) in devices {
            guard let entries = value as? [[String: Any]] else { continue }
            for entry in entries {
                guard
                    (entry["state"] as? String) == "Booted",
                    let name = entry["name"] as? String,
                    let udid = entry["udid"] as? String,
                    let typeID = entry["deviceTypeIdentifier"] as? String
                else { continue }
                result.append(BootedDevice(name: name, udid: udid, deviceTypeIdentifier: typeID))
            }
        }
        return result.sorted { $0.udid < $1.udid }
    }

    /// Return a dictionary from device type identifier to bundle path, from the JSON of
    /// `xcrun simctl list devicetypes -j`.
    public static func deviceTypeBundlePaths(fromDeviceTypesJSON data: Data) throws -> [String: String] {
        guard
            let top = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let types = top["devicetypes"] as? [[String: Any]]
        else {
            throw SimctlParsingError.malformed
        }

        var result: [String: String] = [:]
        for type in types {
            guard
                let identifier = type["identifier"] as? String,
                let bundlePath = type["bundlePath"] as? String
            else { continue }
            result[identifier] = bundlePath
        }
        return result
    }

    /// Read `mainScreenWidth`, `mainScreenHeight` and `mainScreenScale` from a device type's
    /// `profile.plist`. Throws `.malformed` unless all three are present and greater than zero.
    public static func screen(fromProfilePlist data: Data) throws -> ProfileScreen {
        guard let plist = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else {
            throw SimctlParsingError.malformed
        }

        func number(_ key: String) -> CGFloat? {
            guard let n = plist[key] as? NSNumber else { return nil }
            return CGFloat(n.doubleValue)
        }

        guard
            let width = number("mainScreenWidth"), width > 0,
            let height = number("mainScreenHeight"), height > 0,
            let scale = number("mainScreenScale"), scale > 0
        else {
            throw SimctlParsingError.malformed
        }
        return ProfileScreen(pixelWidth: width, pixelHeight: height, scale: scale)
    }

    /// Return the device name in a Simulator window title such as `iPhone 14 Pro Max – iOS 26.5`.
    /// Accepts an en dash or a hyphen with spaces around it as the separator. Returns nothing when
    /// there is no separator or the name is empty.
    public static func deviceName(fromWindowTitle title: String) -> String? {
        let separators = [" \u{2013} ", "\u{2013}", " - "]
        for separator in separators {
            guard let range = title.range(of: separator) else { continue }
            let name = title[title.startIndex..<range.lowerBound]
                .trimmingCharacters(in: .whitespaces)
            return name.isEmpty ? nil : name
        }
        return nil
    }
}
