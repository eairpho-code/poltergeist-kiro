import Foundation

/// Where a click came from: real hardware, or a program that posted it.
public enum ClickOrigin: Equatable {
    case hardware
    case synthetic(sourcePID: Int)

    /// A sender process id of 0 is real hardware; any other id is synthetic.
    public init(sourcePID: Int) {
        self = sourcePID == 0 ? .hardware : .synthetic(sourcePID: sourcePID)
    }
}

/// Who a click is attributed to.
public enum ClickActor: Equatable {
    case human
    case agent
}

/// Decides who made a click from its origin and the sender's names.
public struct ClickPolicy {
    public let agentApps: [String]
    public let includeSynthetic: Bool

    public init(agentApps: [String] = [], includeSynthetic: Bool = false) {
        self.agentApps = agentApps
        self.includeSynthetic = includeSynthetic
    }

    /// The actor for a click, or nothing when the click should be ignored.
    ///
    /// - Hardware clicks are always the human's.
    /// - A synthetic click is the agent's when one of the sender's names matches a configured
    ///   agent app, ignoring case.
    /// - Any other synthetic click is ignored, unless synthetic clicks count as the human's.
    public func actor(for origin: ClickOrigin, senderNames: [String] = []) -> ClickActor? {
        switch origin {
        case .hardware:
            return .human
        case .synthetic:
            if matchesAgent(senderNames) {
                return .agent
            }
            return includeSynthetic ? .human : nil
        }
    }

    private func matchesAgent(_ senderNames: [String]) -> Bool {
        let agents = Set(agentApps.map { $0.lowercased() })
        for name in senderNames where agents.contains(name.lowercased()) {
            return true
        }
        return false
    }
}
