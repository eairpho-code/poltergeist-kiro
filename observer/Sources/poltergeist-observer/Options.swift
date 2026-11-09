import Foundation

/// The parsed command line options for the observer.
struct Options {
    /// The server base URL to post gestures to.
    var server: URL = URL(string: "http://127.0.0.1:8000")!
    /// Whether to include the short label of the element under a click.
    var sendLabels: Bool = false
    /// App names whose synthetic clicks count as the agent's (process name, app name or bundle id).
    var agentApps: [String] = []
    /// Whether synthetic clicks that match no agent app count as the human's.
    var includeSynthetic: Bool = false
    /// Print each gesture instead of posting it, and never contact the server.
    var dryRun: Bool = false
    /// Log why gestures are ignored.
    var verbose: Bool = false

    /// A problem parsing the command line.
    enum ParseError: Error, Equatable {
        /// The user asked for help.
        case help
        /// A bad option or a missing value, with the reason to show.
        case invalid(message: String)
    }

    /// The usage text, explaining each option and the permissions that are needed.
    static let usage = """
    Usage: poltergeist-observer [options]

    Watches the Mac mouse and reports clicks and drags on an iOS Simulator display
    to the Poltergeist server as POST /human-click or POST /agent-click.

    Options:
      --server URL         Server base URL, http or https with a host.
                           Default: http://127.0.0.1:8000
      --send-labels        Include the short label of the element under a click.
                           Off by default for privacy.
      --agent-app NAME     Treat synthetic clicks from this app (process name, app
                           name or bundle identifier) as the agent's. Repeatable.
      --include-synthetic  Count synthetic clicks that match no agent app as the
                           human's instead of ignoring them.
      --dry-run            Print each gesture to standard output and do not contact
                           the server.
      --verbose            Also log why a gesture was ignored. For debugging only;
                           this prints positions of clicks outside a display.
      -h, --help           Print this help and exit.

    Permissions:
      The observer needs both the Accessibility and the Input Monitoring
      permissions in System Settings > Privacy & Security. Without them it cannot
      watch the mouse or read the Simulator display and will exit with an error.
    """

    /// Parse the given arguments (without the program name). Throws `ParseError` for `--help`,
    /// a bad option or a missing value.
    static func parse(_ arguments: [String]) throws -> Options {
        var options = Options()
        var index = arguments.startIndex

        func nextValue(for option: String) throws -> String {
            index = arguments.index(after: index)
            guard index < arguments.endIndex else {
                throw ParseError.invalid(message: "\(option) needs a value")
            }
            return arguments[index]
        }

        while index < arguments.endIndex {
            let argument = arguments[index]
            switch argument {
            case "-h", "--help":
                throw ParseError.help
            case "--server":
                let value = try nextValue(for: "--server")
                options.server = try parseServer(value)
            case "--send-labels":
                options.sendLabels = true
            case "--agent-app":
                let value = try nextValue(for: "--agent-app")
                options.agentApps.append(value)
            case "--include-synthetic":
                options.includeSynthetic = true
            case "--dry-run":
                options.dryRun = true
            case "--verbose":
                options.verbose = true
            default:
                throw ParseError.invalid(message: "unknown option: \(argument)")
            }
            index = arguments.index(after: index)
        }
        return options
    }

    /// Validate a `--server` value: an http or https URL with a host.
    private static func parseServer(_ value: String) throws -> URL {
        guard
            let url = URL(string: value),
            let scheme = url.scheme?.lowercased(),
            scheme == "http" || scheme == "https",
            let host = url.host, !host.isEmpty
        else {
            throw ParseError.invalid(message: "--server must be an http or https URL with a host, got: \(value)")
        }
        return url
    }
}
