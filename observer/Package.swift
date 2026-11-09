// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "poltergeist-observer",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "poltergeist-observer", targets: ["poltergeist-observer"]),
    ],
    targets: [
        // Pure logic: coordinate mapping, request bodies, simctl parsing. No system access.
        .target(name: "ObserverCore"),
        // Mouse tap, Simulator accessibility lookup and the HTTP client.
        .executableTarget(name: "poltergeist-observer", dependencies: ["ObserverCore"]),
        .testTarget(name: "ObserverCoreTests", dependencies: ["ObserverCore"]),
    ]
)
