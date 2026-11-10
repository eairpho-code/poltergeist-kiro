import XCTest
@testable import ObserverCore

final class ElementPickerTests: XCTestCase {
    private func text() -> ElementInfo { ElementInfo(role: "AXStaticText") }
    private func group() -> ElementInfo { ElementInfo(role: "AXGroup") }
    private func button() -> ElementInfo { ElementInfo(role: "AXButton", actions: ["AXPress"]) }

    func testAnInteractiveElementUnderTheClickIsChosen() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [button(), group()]), 0)
    }

    func testTheTextInsideAButtonChoosesTheButton() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [text(), button()]), 1)
    }

    func testTheNearestInteractiveAncestorWins() {
        let link = ElementInfo(role: "AXLink")
        XCTAssertEqual(ElementPicker.chosenIndex(in: [text(), group(), link, button()]), 2)
    }

    func testAnInteractiveAncestorIsNotNeededWhenTheHitIsInteractive() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [button(), button()]), 0)
    }

    func testAnElementWithThePressActionIsInteractiveWhateverItsRole() {
        let pressable = ElementInfo(role: "AXStaticText", actions: ["AXPress"])
        XCTAssertTrue(ElementPicker.isInteractive(pressable))
        XCTAssertEqual(ElementPicker.chosenIndex(in: [pressable, button()]), 0)
    }

    func testOtherActionsDoNotMakeAnElementInteractive() {
        let menu = ElementInfo(role: "AXGroup", actions: ["AXShowMenu", "AXScrollToVisible"])
        XCTAssertFalse(ElementPicker.isInteractive(menu))
    }

    func testEveryInteractiveRoleIsInteractive() {
        let roles = ["AXButton", "AXLink", "AXCell", "AXCheckBox", "AXRadioButton", "AXSwitch",
                     "AXTextField", "AXTextArea", "AXSlider", "AXMenuItem", "AXPopUpButton"]
        for role in roles {
            XCTAssertTrue(ElementPicker.isInteractive(ElementInfo(role: role)), role)
            XCTAssertEqual(ElementPicker.chosenIndex(in: [text(), ElementInfo(role: role)]), 1, role)
        }
    }

    func testPlainRolesAreNotInteractive() {
        for role in ["AXStaticText", "AXImage", "AXGroup", "AXList", "AXScrollArea", ""] {
            XCTAssertFalse(ElementPicker.isInteractive(ElementInfo(role: role)), role)
        }
    }

    func testAnImageInsideACellChoosesTheCell() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [ElementInfo(role: "AXImage"), ElementInfo(role: "AXCell")]), 1)
    }

    func testWithNoInteractiveAncestorTheElementUnderTheClickIsKept() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [text(), group(), group()]), 0)
    }

    func testAWindowOrAnApplicationIsNeverChosen() {
        let window = ElementInfo(role: "AXWindow", actions: ["AXPress"])
        let application = ElementInfo(role: "AXApplication", actions: ["AXPress"])
        XCTAssertFalse(ElementPicker.isInteractive(window))
        XCTAssertFalse(ElementPicker.isInteractive(application))
        XCTAssertEqual(ElementPicker.chosenIndex(in: [text(), group(), window, application]), 0)
    }

    func testOnlyTheNextSixAncestorsAreSearched() {
        XCTAssertEqual(ElementPicker.maxAncestors, 6)
        var near = [text()] + Array(repeating: group(), count: 5)
        near.append(button())                       // index 6: reachable
        XCTAssertEqual(ElementPicker.chosenIndex(in: near), 6)
        var far = [text()] + Array(repeating: group(), count: 6)
        far.append(button())                        // index 7: too far
        XCTAssertEqual(ElementPicker.chosenIndex(in: far), 0)
    }

    func testAChainOfOneIsTheElementItself() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: [text()]), 0)
    }

    func testAnEmptyChainGivesZero() {
        XCTAssertEqual(ElementPicker.chosenIndex(in: []), 0)
    }
}
