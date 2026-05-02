import Foundation
import AVFoundation

class VeraCarPlayClient: NSObject, URLSessionWebSocketDelegate {

    var onResponse: ((String) -> Void)?

    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?
    private var serverUrl: String = ""
    private var shouldReconnect = true
    private var reconnectAttempt = 0
    private let synthesizer = AVSpeechSynthesizer()

    override init() {
        super.init()
        let config = URLSessionConfiguration.default
        urlSession = URLSession(configuration: config, delegate: self, delegateQueue: .main)
    }

    // MARK: - Connection

    func connect(to url: String) {
        serverUrl = url
        shouldReconnect = true
        reconnectAttempt = 0
        doConnect()
    }

    private func doConnect() {
        // Append API key if configured
        var urlString = serverUrl
        if let apiKey = UserDefaults(suiteName: "group.com.patchava.vera")?.string(forKey: "api_key"),
           !apiKey.isEmpty {
            let separator = urlString.contains("?") ? "&" : "?"
            urlString += "\(separator)api_key=\(apiKey)"
        }
        guard let url = URL(string: urlString) else { return }

        var request = URLRequest(url: url)
        request.setValue("carplay", forHTTPHeaderField: "X-Vera-Client")
        webSocketTask = urlSession?.webSocketTask(with: request)
        webSocketTask?.resume()

        let hello: [String: Any] = [
            "type": "hello",
            "client": "carplay",
            "version": "1.0.3"
        ]
        if let data = try? JSONSerialization.data(withJSONObject: hello),
           let str = String(data: data, encoding: .utf8) {
            webSocketTask?.send(.string(str)) { _ in }
        }

        receiveMessage()
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleMessage(text)
                default:
                    break
                }
                self?.receiveMessage()

            case .failure:
                self?.reconnectWithBackoff()
            }
        }
    }

    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String,
              (type == "response" || type == "agent_response") else {
            return
        }

        let content = (json["data"] as? String) ?? (json["message"] as? String) ?? ""
        if !content.isEmpty {
            onResponse?(content)
        }
    }

    // MARK: - Reconnection

    private func reconnectWithBackoff() {
        guard shouldReconnect else { return }
        reconnectAttempt += 1
        let delay = min(30.0, Double(1 << min(reconnectAttempt, 5)))
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self = self, self.shouldReconnect else { return }
            self.doConnect()
        }
    }

    // MARK: - Send

    func sendTranscript(_ text: String) {
        let message: [String: Any] = [
            "type": "transcript",
            "data": text
        ]
        if let data = try? JSONSerialization.data(withJSONObject: message),
           let str = String(data: data, encoding: .utf8) {
            webSocketTask?.send(.string(str)) { _ in }
        }
    }

    // MARK: - TTS

    func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        synthesizer.speak(utterance)
    }

    // MARK: - Disconnect

    func disconnect() {
        shouldReconnect = false
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        synthesizer.stopSpeaking(at: .immediate)
    }

    // MARK: - URLSessionWebSocketDelegate

    func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didOpenWithProtocol protocol: String?
    ) {
        reconnectAttempt = 0
    }

    func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
        reason: Data?
    ) {
        // Don't reconnect on auth denied (4001) or rate limit (4029)
        let code = closeCode.rawValue
        if code != 4001 && code != 4029 {
            reconnectWithBackoff()
        }
    }
}
