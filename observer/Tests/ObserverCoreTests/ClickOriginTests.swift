import XCTest
@testable import ObserverCore

final class ClickOriginTests: XCTestCase {
    func testProcessIdZeroIsHardware() {
        XCTAssertEqual(ClickOrigin(sourcePID: 0), .hardware)
    }

    func testAnyOtherProcessIdIsSynthetic() {
        XCTAssertEqual(ClickOrigin(sourcePID: 2605), .synthetic(sourcePID: 2605))
        XCTAssertEqual(ClickOrigin(sourcePID: 1), .synthetic(sourcePID: 1))
    }

    func testHardwareClicksAreAlwaysTheHumans() {
        XCTAssertEqual(ClickPolicy().actor(for: .hardware), .human)
        XCTAssertEqual(ClickPolicy(agentApps: ["Claude"]).actor(for: .hardware), .human)
    }

    func testSyntheticClicksAreIgnoredByDefault() {
        let policy = ClickPolicy()
        XCTAssertNil(policy.actor(for: .synthetic(sourcePID: 2605), senderNames: ["Claude"]))
    }

    func testSyntheticClickFromAnAgentAppIsTheAgents() {
        let policy = ClickPolicy(agentApps: ["Claude"])
        XCTAssertEqual(policy.actor(for: .synthetic(sourcePID: 2605), senderNames: ["Claude"]), .agent)
    }

    func testAgentAppMatchingIgnoresCase() {
        let policy = ClickPolicy(agentApps: ["claude"])
        XCTAssertEqual(policy.actor(for: .synthetic(sourcePID: 1), senderNames: ["CLAUDE"]), .agent)
    }

    func testAgentAppMatchesAnyOfTheSendersNames() {
        let policy = ClickPolicy(agentApps: ["com.anthropic.claudefordesktop"])
        let names = ["Claude", "com.anthropic.claudefordesktop"]
        XCTAssertEqual(policy.actor(for: .synthetic(sourcePID: 1), senderNames: names), .agent)
    }

    func testAgentAppNamesMustMatchExactly() {
        // "Clau" must not match "Claude", or a program with a similar name would count as the agent.
        let policy = ClickPolicy(agentApps: ["Clau"])
        XCTAssertNil(policy.actor(for: .synthetic(sourcePID: 1), senderNames: ["Claude"]))
    }

    func testOtherSyntheticClicksCanCountAsTheHumans() {
        let policy = ClickPolicy(agentApps: ["Claude"], includeSynthetic: true)
        XCTAssertEqual(policy.actor(for: .synthetic(sourcePID: 9), senderNames: ["ToDesk"]), .human)
        XCTAssertEqual(policy.actor(for: .synthetic(sourcePID: 2605), senderNames: ["Claude"]), .agent)
    }
}
