import CoreGraphics
import XCTest
@testable import ObserverCore

final class SimulatorScreenTests: XCTestCase {
    // iPhone 14 Pro Max: 1290 x 2796 pixels at 3x is 430 x 932 points.
    let phone = DeviceProfile(name: "iPhone 14 Pro Max", pixelWidth: 1290, pixelHeight: 2796, scale: 3)

    func testPointSizeIsPixelsDividedByScale() {
        XCTAssertEqual(phone.pointSize, CGSize(width: 430, height: 932))
    }

    func testClickAtTheTopLeftCornerIsTheOrigin() {
        let screen = SimulatorScreen(rect: CGRect(x: 69, y: 131, width: 430, height: 932), device: phone)
        let point = screen.devicePoint(forGlobal: CGPoint(x: 69, y: 131))
        XCTAssertEqual(point, CGPoint(x: 0, y: 0))
    }

    func testWindowAtFullSizeMapsOneToOne() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        let point = screen.devicePoint(forGlobal: CGPoint(x: 210, y: 150))
        XCTAssertEqual(point, CGPoint(x: 110, y: 100))
    }

    func testZoomedOutWindowScalesBackToDevicePoints() {
        // The Simulator window shown at half size: 215 x 466 Mac points.
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 200, width: 215, height: 466), device: phone)
        let point = screen.devicePoint(forGlobal: CGPoint(x: 100 + 107.5, y: 200 + 233))
        XCTAssertEqual(point?.x ?? -1, 215, accuracy: 0.001)
        XCTAssertEqual(point?.y ?? -1, 466, accuracy: 0.001)
    }

    func testTheSameDevicePointComesOutAtAnyZoom() {
        let big = SimulatorScreen(rect: CGRect(x: 0, y: 0, width: 430, height: 932), device: phone)
        let small = SimulatorScreen(rect: CGRect(x: 300, y: 40, width: 325, height: 705.7), device: phone)
        // 25% across and 40% down the display, whatever its size.
        let a = big.devicePoint(forGlobal: CGPoint(x: 0.25 * 430, y: 0.4 * 932))
        let b = small.devicePoint(forGlobal: CGPoint(x: 300 + 0.25 * 325, y: 40 + 0.4 * 705.7))
        XCTAssertEqual(a?.x ?? -1, b?.x ?? -2, accuracy: 0.01)
        XCTAssertEqual(a?.y ?? -1, b?.y ?? -2, accuracy: 0.01)
    }

    func testClickOutsideTheDisplayIsNil() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 100, width: 430, height: 932), device: phone)
        XCTAssertNil(screen.devicePoint(forGlobal: CGPoint(x: 99, y: 500)))
        XCTAssertNil(screen.devicePoint(forGlobal: CGPoint(x: 300, y: 1100)))
        // The right and bottom edges are outside, like CGRect.contains says.
        XCTAssertNil(screen.devicePoint(forGlobal: CGPoint(x: 530, y: 500)))
    }

    func testRotatedSimulatorSwapsWidthAndHeight() {
        // Landscape: the display is wider than tall, so it spans 932 x 430 device points.
        let screen = SimulatorScreen(rect: CGRect(x: 0, y: 0, width: 466, height: 215), device: phone)
        XCTAssertEqual(screen.displayedPointSize, CGSize(width: 932, height: 430))
        let point = screen.devicePoint(forGlobal: CGPoint(x: 233, y: 107.5))
        XCTAssertEqual(point?.x ?? -1, 466, accuracy: 0.001)
        XCTAssertEqual(point?.y ?? -1, 215, accuracy: 0.001)
    }

    func testEmptyRectNeverMatches() {
        let screen = SimulatorScreen(rect: .zero, device: phone)
        XCTAssertNil(screen.devicePoint(forGlobal: .zero))
    }

    func testLookupFindsTheDisplayUnderTheClick() {
        let left = SimulatorScreen(rect: CGRect(x: 0, y: 0, width: 215, height: 466), device: phone)
        let right = SimulatorScreen(rect: CGRect(x: 400, y: 0, width: 215, height: 466), device: phone)
        XCTAssertEqual(ScreenLookup.screen(containing: CGPoint(x: 450, y: 10), in: [left, right]), right)
        XCTAssertEqual(ScreenLookup.screen(containing: CGPoint(x: 10, y: 10), in: [left, right]), left)
        XCTAssertNil(ScreenLookup.screen(containing: CGPoint(x: 300, y: 10), in: [left, right]))
    }

    func testClampedPointInsideTheDisplayMatchesTheNormalMapping() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        let inside = CGPoint(x: 210, y: 150)
        XCTAssertEqual(screen.devicePointClamped(forGlobal: inside), screen.devicePoint(forGlobal: inside))
    }

    func testClampedPointOutsideTheDisplayLandsOnTheNearestEdge() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        // Above the display and to the left of it: the top left corner.
        XCTAssertEqual(screen.devicePointClamped(forGlobal: CGPoint(x: 0, y: 0)), CGPoint(x: 0, y: 0))
        // Below and to the right: the bottom right corner.
        XCTAssertEqual(screen.devicePointClamped(forGlobal: CGPoint(x: 5000, y: 5000)), CGPoint(x: 430, y: 932))
        // Only past the top: x is kept, y becomes 0.
        XCTAssertEqual(screen.devicePointClamped(forGlobal: CGPoint(x: 310, y: -40)), CGPoint(x: 210, y: 0))
    }

    func testClampedPointOfAnEmptyRectIsNil() {
        XCTAssertNil(SimulatorScreen(rect: .zero, device: phone).devicePointClamped(forGlobal: .zero))
    }

    func testAPressJustOutsideTheEdgeCountsWithTheTolerance() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        let belowTheBottomEdge = CGPoint(x: 300, y: 982.8)
        XCTAssertNil(ScreenLookup.screen(containing: belowTheBottomEdge, in: [screen]))
        XCTAssertEqual(
            ScreenLookup.screen(containing: belowTheBottomEdge, in: [screen], edgeTolerance: ScreenLookup.edgeTolerance),
            screen
        )
    }

    func testAPressFarOutsideTheDisplayStillDoesNotCount() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        let farBelow = CGPoint(x: 300, y: 990)
        XCTAssertNil(ScreenLookup.screen(containing: farBelow, in: [screen], edgeTolerance: ScreenLookup.edgeTolerance))
    }

    func testAnEdgePressIsMappedOntoTheEdge() {
        let screen = SimulatorScreen(rect: CGRect(x: 100, y: 50, width: 430, height: 932), device: phone)
        XCTAssertEqual(screen.devicePointClamped(forGlobal: CGPoint(x: 300, y: 982.8)), CGPoint(x: 200, y: 932))
    }
}
