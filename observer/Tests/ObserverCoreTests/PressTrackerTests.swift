import CoreGraphics
import XCTest
@testable import ObserverCore

final class PressTrackerTests: XCTestCase {
    func testPressAndReleaseInTheSamePlaceIsAClick() {
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 100, y: 200), sourcePID: 0)
        let gesture = tracker.release(at: CGPoint(x: 101, y: 201), sourcePID: 0)
        XCTAssertEqual(gesture, .click(at: CGPoint(x: 100, y: 200), origin: .hardware))
    }

    func testTheClickIsReportedWhereThePressHappened() {
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 10, y: 10), sourcePID: 0)
        let gesture = tracker.release(at: CGPoint(x: 15, y: 10), sourcePID: 0)
        XCTAssertEqual(gesture, .click(at: CGPoint(x: 10, y: 10), origin: .hardware))
    }

    func testMovingFarBetweenPressAndReleaseIsADrag() {
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 100, y: 500), sourcePID: 0)
        let gesture = tracker.release(at: CGPoint(x: 100, y: 200), sourcePID: 0)
        XCTAssertEqual(gesture, .drag(from: CGPoint(x: 100, y: 500), to: CGPoint(x: 100, y: 200), origin: .hardware))
    }

    func testTheTravelLimitIsInclusive() {
        var tracker = PressTracker(maxClickTravel: 8)
        tracker.press(at: .zero, sourcePID: 0)
        XCTAssertEqual(tracker.release(at: CGPoint(x: 8, y: 0), sourcePID: 0), .click(at: .zero, origin: .hardware))
        tracker.press(at: .zero, sourcePID: 0)
        if case .drag? = tracker.release(at: CGPoint(x: 8.1, y: 0), sourcePID: 0) {} else {
            XCTFail("8.1 points of travel should be a drag")
        }
    }

    func testReleaseWithoutAPressIsNothing() {
        var tracker = PressTracker()
        XCTAssertNil(tracker.release(at: .zero, sourcePID: 0))
    }

    func testOneReleaseCompletesOnlyOneGesture() {
        var tracker = PressTracker()
        tracker.press(at: .zero, sourcePID: 0)
        XCTAssertNotNil(tracker.release(at: .zero, sourcePID: 0))
        XCTAssertNil(tracker.release(at: .zero, sourcePID: 0))
    }

    func testAnAgentClickInTheMiddleOfAHumanPressDoesNotDisturbIt() {
        // The person presses and holds; the AI clicks elsewhere; the person releases.
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 50, y: 60), sourcePID: 0)
        tracker.press(at: CGPoint(x: 300, y: 400), sourcePID: 2605)
        let agent = tracker.release(at: CGPoint(x: 300, y: 400), sourcePID: 2605)
        let human = tracker.release(at: CGPoint(x: 50, y: 60), sourcePID: 0)

        XCTAssertEqual(agent, .click(at: CGPoint(x: 300, y: 400), origin: .synthetic(sourcePID: 2605)))
        XCTAssertEqual(human, .click(at: CGPoint(x: 50, y: 60), origin: .hardware))
    }

    func testAHumanDragIsStillADragWhileTheAgentClicks() {
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 100, y: 500), sourcePID: 0)
        tracker.press(at: CGPoint(x: 300, y: 400), sourcePID: 2605)
        _ = tracker.release(at: CGPoint(x: 300, y: 400), sourcePID: 2605)
        let human = tracker.release(at: CGPoint(x: 100, y: 200), sourcePID: 0)

        XCTAssertEqual(human, .drag(from: CGPoint(x: 100, y: 500), to: CGPoint(x: 100, y: 200), origin: .hardware))
    }

    func testEachSenderKeepsItsOwnPress() {
        var tracker = PressTracker()
        tracker.press(at: CGPoint(x: 1, y: 1), sourcePID: 7)
        tracker.press(at: CGPoint(x: 2, y: 2), sourcePID: 9)
        XCTAssertEqual(tracker.release(at: CGPoint(x: 1, y: 1), sourcePID: 7), .click(at: CGPoint(x: 1, y: 1), origin: .synthetic(sourcePID: 7)))
        XCTAssertEqual(tracker.release(at: CGPoint(x: 2, y: 2), sourcePID: 9), .click(at: CGPoint(x: 2, y: 2), origin: .synthetic(sourcePID: 9)))
    }
}
