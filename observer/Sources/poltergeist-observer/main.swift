import ApplicationServices
import AppKit
import CoreGraphics
import Darwin
import Foundation
import ObserverCore

// MARK: - Logging

/// Write a line to standard error. All diagnostics go to stderr; `--dry-run` payloads go to stdout.
func logLine(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

// MARK: - Parse options

let arguments = Array(CommandLine.arguments.dropFirst())
let options: Options
do {
    options = try Options.parse(arguments)
} catch Options.ParseError.help {
    print(Options.usage)
    exit(0)
} catch let Options.ParseError.invalid(message) {
    logLine("error: \(message)")
    logLine(Options.usage)
    exit(2)
} catch {
    logLine("error: \(error)")
    logLine(Options.usage)
    exit(2)
}

// MARK: - Accessibility permission

// A real run needs Accessibility and exits 1 with an explanation when it is missing. This holds
// in every mode, including a dry run.
let accessibilityTrusted = AXIsProcessTrusted()
if !accessibilityTrusted {
    logLine("""
    error: Accessibility permission is not granted. The observer needs it to read the
    Simulator display. Grant it in System Settings > Privacy & Security > Accessibility.
    """)
    exit(1)
}

// MARK: - Build the pieces

let policy = ClickPolicy(agentApps: options.agentApps, includeSynthetic: options.includeSynthetic)
let screens = SimulatorScreens()
let client = ServerClient(baseURL: options.server)
let tap = ClickTap()

// Gestures are handled off the event-tap thread so a slow lookup cannot stall the mouse.
let work = DispatchQueue(label: "poltergeist-observer.gestures")

// MARK: - Gesture handling

func actorName(_ actor: ClickActor) -> String { actor == .human ? "human" : "agent" }

/// The names of the process that posted a synthetic click: its process name and executable name
/// (which exist even for a command line process with no bundle), and its app name and bundle
/// identifier when it is a GUI application. Hardware clicks have no sender process, so no names.
func senderNames(for origin: ClickOrigin) -> [String] {
    guard case let .synthetic(sourcePID) = origin else { return [] }
    let pid = pid_t(sourcePID)

    var names: [String] = []

    // A GUI application: bundle identifier and localized app name, when present.
    if let app = NSRunningApplication(processIdentifier: pid) {
        if let bundleID = app.bundleIdentifier { names.append(bundleID) }
        if let localizedName = app.localizedName { names.append(localizedName) }
    }

    // The process name and executable name, which a command line process has even with no bundle.
    var nameBuffer = [CChar](repeating: 0, count: 256)
    if proc_name(Int32(pid), &nameBuffer, UInt32(nameBuffer.count)) > 0 {
        let processName = String(cString: nameBuffer)
        if !processName.isEmpty { names.append(processName) }
    }

    // PROC_PIDPATHINFO_MAXSIZE (4 * MAXPATHLEN) is not importable into Swift, so use its value.
    var pathBuffer = [CChar](repeating: 0, count: 4 * Int(MAXPATHLEN))
    if proc_pidpath(Int32(pid), &pathBuffer, UInt32(pathBuffer.count)) > 0 {
        let executableName = (String(cString: pathBuffer) as NSString).lastPathComponent
        if !executableName.isEmpty { names.append(executableName) }
    }

    return names
}

/// Resolve the device points, actor and element for a gesture, then report it.
func handleGesture(
    start: CGPoint,
    end: CGPoint?,
    origin: ClickOrigin
) {
    // Who clicked. Synthetic clicks need the sender's names to match an agent app.
    let senderNames = senderNames(for: origin)
    guard let actor = policy.actor(for: origin, senderNames: senderNames) else {
        if options.verbose {
            logLine("ignored: synthetic click from \(senderNames.joined(separator: ", ")) is not an agent app")
        }
        return
    }

    // Must start on a Simulator display, with the edge tolerance.
    let currentScreens = screens.current()
    guard let screen = ScreenLookup.screen(
        containing: start, in: currentScreens, edgeTolerance: ScreenLookup.edgeTolerance
    ) else {
        if options.verbose {
            logLine("ignored: click at (\(start.x), \(start.y)) is not on a Simulator display")
        }
        return
    }

    // The Simulator must be the top application at that point.
    guard screens.simulatorIsOnTop(atGlobal: start) else {
        if options.verbose {
            logLine("ignored: the Simulator is not the top application at (\(start.x), \(start.y))")
        }
        return
    }

    guard let startDevice = screen.devicePoint(forGlobal: start) else {
        if options.verbose {
            logLine("ignored: could not map (\(start.x), \(start.y)) to device points")
        }
        return
    }

    let element = screens.element(atGlobal: start, includeLabel: options.sendLabels)

    let payload: ClickPayload
    let kind: String
    if let end = end, let endDevice = screen.devicePointClamped(forGlobal: end) {
        payload = ClickPayload(
            devicePointX: Double(startDevice.x), y: Double(startDevice.y),
            endX: Double(endDevice.x), endY: Double(endDevice.y),
            uiElement: element
        )
        kind = "drag"
    } else {
        payload = ClickPayload(
            devicePointX: Double(startDevice.x), y: Double(startDevice.y),
            uiElement: element
        )
        kind = "click"
    }

    report(payload: payload, actor: actor, kind: kind)
}

/// Report a gesture: print it in dry-run mode, otherwise post it to the server.
func report(payload: ClickPayload, actor: ClickActor, kind: String) {
    let actorText = actorName(actor)
    let json = (try? payload.jsonData()).flatMap { String(data: $0, encoding: .utf8) } ?? "{}"

    if options.dryRun {
        print("\(actorText) \(kind) \(json)")
        return
    }

    logLine("reported \(actorText) \(kind): \(json)")
    client.post(payload: payload, actor: actor) { result in
        switch result {
        case let .response(status, body):
            if status >= 400 {
                logLine("server error \(status) for \(actorText) \(kind): \(body)")
            }
        case let .failure(message):
            logLine("could not reach the server for \(actorText) \(kind): \(message)")
        }
    }
}

tap.onClick = { point, origin in
    work.async { handleGesture(start: point, end: nil, origin: origin) }
}
tap.onDrag = { from, to, origin in
    work.async { handleGesture(start: from, end: to, origin: origin) }
}

// MARK: - Start the tap

if !tap.start() {
    logLine("""
    error: macOS refused the event tap. The observer needs the Input Monitoring
    permission to watch the mouse. Grant it in System Settings > Privacy & Security >
    Input Monitoring. Accessibility is also required.
    """)
    exit(1)
}

// MARK: - Signal handlers

func installSignalHandler(_ signalNumber: Int32) {
    signal(signalNumber, SIG_IGN)
    let source = DispatchSource.makeSignalSource(signal: signalNumber, queue: .main)
    source.setEventHandler {
        logLine("stopping")
        exit(0)
    }
    source.resume()
    // Keep the source alive for the lifetime of the process.
    signalSources.append(source)
}

var signalSources: [DispatchSourceSignal] = []
installSignalHandler(SIGINT)
installSignalHandler(SIGTERM)

// MARK: - Run

logLine("Watching clicks in the iOS Simulator, reporting to \(options.server.absoluteString)\(options.dryRun ? " (dry run)" : "")")
CFRunLoopRun()
