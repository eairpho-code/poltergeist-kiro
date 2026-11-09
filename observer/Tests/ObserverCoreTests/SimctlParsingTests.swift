import Foundation
import XCTest
@testable import ObserverCore

final class SimctlParsingTests: XCTestCase {
    private let devicesJSON = """
    {
      "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-26-5": [
          {"name": "iPhone 14 Pro Max", "udid": "BBBB", "state": "Booted",
           "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-14-Pro-Max"},
          {"name": "iPhone 14 Pro Max QA", "udid": "AAAA", "state": "Shutdown",
           "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-14-Pro-Max"}
        ],
        "com.apple.CoreSimulator.SimRuntime.iOS-18-0": [
          {"name": "iPhone SE", "udid": "CCCC", "state": "Booted",
           "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-SE"}
        ]
      }
    }
    """

    func testOnlyBootedDevicesAreReturned() throws {
        let devices = try SimctlParsing.bootedDevices(fromDevicesJSON: Data(devicesJSON.utf8))
        XCTAssertEqual(devices.map(\.udid), ["BBBB", "CCCC"])
        XCTAssertEqual(devices.first?.name, "iPhone 14 Pro Max")
        XCTAssertEqual(devices.first?.deviceTypeIdentifier, "com.apple.CoreSimulator.SimDeviceType.iPhone-14-Pro-Max")
    }

    func testNoBootedDevicesIsAnEmptyList() throws {
        let json = #"{"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-26-5": []}}"#
        XCTAssertEqual(try SimctlParsing.bootedDevices(fromDevicesJSON: Data(json.utf8)), [])
    }

    func testMalformedDevicesJSONThrows() {
        XCTAssertThrowsError(try SimctlParsing.bootedDevices(fromDevicesJSON: Data(#"{"nope": 1}"#.utf8)))
        XCTAssertThrowsError(try SimctlParsing.bootedDevices(fromDevicesJSON: Data("not json".utf8)))
    }

    func testDeviceTypeBundlePathsAreIndexedByIdentifier() throws {
        let json = """
        {"devicetypes": [
          {"name": "iPhone 14 Pro Max",
           "identifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-14-Pro-Max",
           "bundlePath": "/Library/Developer/CoreSimulator/Profiles/DeviceTypes/iPhone 14 Pro Max.simdevicetype"},
          {"name": "broken entry"}
        ]}
        """
        let paths = try SimctlParsing.deviceTypeBundlePaths(fromDeviceTypesJSON: Data(json.utf8))
        XCTAssertEqual(paths.count, 1)
        XCTAssertEqual(
            paths["com.apple.CoreSimulator.SimDeviceType.iPhone-14-Pro-Max"],
            "/Library/Developer/CoreSimulator/Profiles/DeviceTypes/iPhone 14 Pro Max.simdevicetype"
        )
    }

    func testProfilePlistGivesPixelsAndScale() throws {
        // Same keys and value types as a real simdevicetype profile.plist.
        let plist = """
        <?xml version="1.0" encoding="UTF-8"?>
        <plist version="1.0"><dict>
          <key>mainScreenHeight</key><integer>2796</integer>
          <key>mainScreenScale</key><real>3</real>
          <key>mainScreenWidth</key><integer>1290</integer>
        </dict></plist>
        """
        let screen = try SimctlParsing.screen(fromProfilePlist: Data(plist.utf8))
        XCTAssertEqual(screen, ProfileScreen(pixelWidth: 1290, pixelHeight: 2796, scale: 3))
    }

    func testProfilePlistWithoutScreenKeysThrows() {
        let plist = #"<?xml version="1.0"?><plist version="1.0"><dict><key>a</key><integer>1</integer></dict></plist>"#
        XCTAssertThrowsError(try SimctlParsing.screen(fromProfilePlist: Data(plist.utf8)))
    }

    func testProfilePlistWithZeroScaleThrows() {
        let plist = """
        <?xml version="1.0"?><plist version="1.0"><dict>
          <key>mainScreenHeight</key><integer>10</integer>
          <key>mainScreenScale</key><real>0</real>
          <key>mainScreenWidth</key><integer>10</integer>
        </dict></plist>
        """
        XCTAssertThrowsError(try SimctlParsing.screen(fromProfilePlist: Data(plist.utf8)))
    }

    func testDeviceNameComesFromTheWindowTitle() {
        XCTAssertEqual(SimctlParsing.deviceName(fromWindowTitle: "iPhone 14 Pro Max \u{2013} iOS 26.5"), "iPhone 14 Pro Max")
        XCTAssertEqual(SimctlParsing.deviceName(fromWindowTitle: "iPad Pro 13-inch (M4) - iOS 18.0"), "iPad Pro 13-inch (M4)")
        XCTAssertNil(SimctlParsing.deviceName(fromWindowTitle: "Simulator"))
        XCTAssertNil(SimctlParsing.deviceName(fromWindowTitle: ""))
    }
}
