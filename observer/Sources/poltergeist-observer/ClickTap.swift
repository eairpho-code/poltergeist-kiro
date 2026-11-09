import CoreGraphics
import Foundation
import ObserverCore

/// A listen-only mouse tap. It watches left mouse presses and releases, turns them into clicks
/// and drags with a `PressTracker`, and never changes or blocks an event.
final class ClickTap {
    /// Called for a completed click at a global point, with the sender's origin.
    var onClick: ((CGPoint, ClickOrigin) -> Void)?
    /// Called for a completed drag between two global points, with the sender's origin.
    var onDrag: ((CGPoint, CGPoint, ClickOrigin) -> Void)?

    private var tracker = PressTracker()
    private var tap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?

    /// Create the tap and add it to the current run loop. Returns false when macOS refuses the tap,
    /// which means Input Monitoring (or Accessibility) is not granted.
    func start() -> Bool {
        let mask: CGEventMask =
            (1 << CGEventType.leftMouseDown.rawValue) |
            (1 << CGEventType.leftMouseUp.rawValue)

        // `self` is passed as the callback's user info so the C callback can reach this instance.
        let userInfo = Unmanaged.passUnretained(self).toOpaque()

        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .listenOnly,
            eventsOfInterest: mask,
            callback: { _, type, event, refcon in
                guard let refcon = refcon else { return Unmanaged.passUnretained(event) }
                let tap = Unmanaged<ClickTap>.fromOpaque(refcon).takeUnretainedValue()
                tap.handle(type: type, event: event)
                // Listen-only: always pass the event through unchanged.
                return Unmanaged.passUnretained(event)
            },
            userInfo: userInfo
        ) else {
            return false
        }

        self.tap = tap
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        self.runLoopSource = source
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    private func handle(type: CGEventType, event: CGEvent) {
        // macOS disables a tap that is slow or after the system sleeps; switch it back on.
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if let tap = tap {
                CGEvent.tapEnable(tap: tap, enable: true)
            }
            return
        }

        let pid = Int(event.getIntegerValueField(.eventSourceUnixProcessID))
        let location = event.location

        switch type {
        case .leftMouseDown:
            tracker.press(at: location, sourcePID: pid)
        case .leftMouseUp:
            guard let gesture = tracker.release(at: location, sourcePID: pid) else { return }
            switch gesture {
            case let .click(at, origin):
                onClick?(at, origin)
            case let .drag(from, to, origin):
                onDrag?(from, to, origin)
            }
        default:
            break
        }
    }
}
