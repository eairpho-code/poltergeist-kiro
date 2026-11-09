import Foundation
import ObserverCore

/// Posts gestures to the Poltergeist server over HTTP.
final class ServerClient {
    /// The outcome of a post: the server's reply, or the error that stopped it.
    enum Result {
        /// The server answered with this status code and body text.
        case response(status: Int, body: String)
        /// The request could not be sent or no reply arrived.
        case failure(message: String)
    }

    private let baseURL: URL
    private let session: URLSession

    /// - Parameters:
    ///   - baseURL: the server base URL (for example `http://127.0.0.1:8000`).
    ///   - timeout: the per-request timeout, 3 seconds by default.
    init(baseURL: URL, timeout: TimeInterval = 3) {
        self.baseURL = baseURL
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = timeout
        configuration.timeoutIntervalForResource = timeout
        self.session = URLSession(configuration: configuration)
    }

    /// Post a payload. A human gesture goes to `/human-click`, an agent gesture to `/agent-click`.
    /// The result is delivered to `completion`.
    func post(payload: ClickPayload, actor: ClickActor, completion: @escaping (Result) -> Void) {
        let path = actor == .human ? "/human-click" : "/agent-click"
        let url = baseURL.appendingPathComponent(path)

        let body: Data
        do {
            body = try payload.jsonData()
        } catch {
            completion(.failure(message: "could not encode payload: \(error)"))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body

        let task = session.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(message: error.localizedDescription))
                return
            }
            guard let http = response as? HTTPURLResponse else {
                completion(.failure(message: "no HTTP response"))
                return
            }
            let text = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            completion(.response(status: http.statusCode, body: text))
        }
        task.resume()
    }
}
