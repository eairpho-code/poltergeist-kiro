import Foundation
import XCTest
@testable import ObserverCore

final class ClickPayloadTests: XCTestCase {
    private func json(_ payload: ClickPayload) throws -> [String: Any] {
        let object = try JSONSerialization.jsonObject(with: payload.jsonData())
        return try XCTUnwrap(object as? [String: Any])
    }

    func testBodyUsesTheKeysTheServerExpects() throws {
        let body = try json(ClickPayload(devicePointX: 110, y: 105))
        XCTAssertEqual(body["x"] as? Double, 110)
        XCTAssertEqual(body["y"] as? Double, 105)
        XCTAssertEqual(body["coordinate_space"] as? String, "device_points")
        XCTAssertEqual(body["scale_factor"] as? Double, 1.0)
    }

    func testNoElementMeansNoUiElementKey() throws {
        let body = try json(ClickPayload(devicePointX: 1, y: 2))
        XCTAssertNil(body["ui_element"])
    }

    func testElementIsNestedWithRoleAndLabel() throws {
        let payload = ClickPayload(devicePointX: 1, y: 2, uiElement: UIElementPayload(role: "button", label: "OK"))
        let element = try XCTUnwrap(try json(payload)["ui_element"] as? [String: Any])
        XCTAssertEqual(element["role"] as? String, "button")
        XCTAssertEqual(element["label"] as? String, "OK")
    }

    func testRoleOnlyElementHasNoLabelKey() throws {
        let payload = ClickPayload(devicePointX: 1, y: 2, uiElement: UIElementPayload(role: "button"))
        let element = try XCTUnwrap(try json(payload)["ui_element"] as? [String: Any])
        XCTAssertNil(element["label"])
    }

    func testPositionsAreRoundedToTwoDecimals() {
        let payload = ClickPayload(devicePointX: 110.123456, y: 99.999)
        XCTAssertEqual(payload.x, 110.12)
        XCTAssertEqual(payload.y, 100.0)
    }

    func testLabelsAreTrimmedAndCutToFiftyCharacters() {
        XCTAssertEqual(Labels.short("  Submit \n"), "Submit")
        XCTAssertEqual(Labels.short(String(repeating: "a", count: 80)), String(repeating: "a", count: 50))
        XCTAssertEqual(Labels.short(String(repeating: "b", count: 50)), String(repeating: "b", count: 50))
    }

    func testEmptyLabelsAreDropped() {
        XCTAssertNil(Labels.short(nil))
        XCTAssertNil(Labels.short(""))
        XCTAssertNil(Labels.short("  \n "))
    }

    func testLabelCutCountsCharactersNotBytes() {
        let label = String(repeating: "地", count: 60)
        XCTAssertEqual(Labels.short(label)?.count, 50)
    }

    func testKnownAccessibilityRolesGetShortNames() {
        XCTAssertEqual(RoleNames.name(forAXRole: "AXButton"), "button")
        XCTAssertEqual(RoleNames.name(forAXRole: "AXTextField"), "text_field")
        XCTAssertEqual(RoleNames.name(forAXRole: "AXStaticText"), "text")
        XCTAssertEqual(RoleNames.name(forAXRole: "AXSlider"), "slider")
    }

    func testUnknownRolesFallBackToSnakeCase() {
        XCTAssertEqual(RoleNames.name(forAXRole: "AXDisclosureTriangle"), "disclosure_triangle")
        XCTAssertEqual(RoleNames.name(forAXRole: "Widget"), "widget")
        XCTAssertEqual(RoleNames.name(forAXRole: "AX"), "unknown")
    }

    func testAClickHasNoEndKeys() throws {
        let body = try json(ClickPayload(devicePointX: 1, y: 2))
        XCTAssertNil(body["end_x"])
        XCTAssertNil(body["end_y"])
    }

    func testADragCarriesItsEndPoint() throws {
        let body = try json(ClickPayload(devicePointX: 215, y: 800, endX: 214.567, endY: 300))
        XCTAssertEqual(body["x"] as? Double, 215)
        XCTAssertEqual(body["y"] as? Double, 800)
        XCTAssertEqual(body["end_x"] as? Double, 214.57)
        XCTAssertEqual(body["end_y"] as? Double, 300)
        XCTAssertEqual(body["coordinate_space"] as? String, "device_points")
    }

    func testADragKeepsItsElement() throws {
        let payload = ClickPayload(devicePointX: 1, y: 2, endX: 3, endY: 4, uiElement: UIElementPayload(role: "slider"))
        let element = try XCTUnwrap(try json(payload)["ui_element"] as? [String: Any])
        XCTAssertEqual(element["role"] as? String, "slider")
    }
}
