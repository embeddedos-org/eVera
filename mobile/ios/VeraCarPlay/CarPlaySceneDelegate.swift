import CarPlay
import Foundation

class CarPlaySceneDelegate: UIResponder, CPTemplateApplicationSceneDelegate {

    private var interfaceController: CPInterfaceController?
    private let client = VeraCarPlayClient()
    private var messages: [(role: String, content: String)] = []

    override init() {
        self.interfaceController = nil
        super.init()
    }

    // MARK: - CPTemplateApplicationSceneDelegate

    func templateApplicationScene(
        _ templateApplicationScene: CPTemplateApplicationScene,
        didConnect interfaceController: CPInterfaceController
    ) {
        self.interfaceController = interfaceController

        client.onResponse = { [weak self] response in
            self?.handleResponse(response)
        }

        let defaults = UserDefaults(suiteName: "group.com.patchava.vera")
        let serverUrl = defaults?.string(forKey: "server_url")
            ?? "ws://192.168.1.100:8000/ws"
        client.connect(to: serverUrl)

        let rootTemplate = buildRootTemplate()
        interfaceController.setRootTemplate(rootTemplate, animated: true, completion: nil)
    }

    func templateApplicationScene(
        _ templateApplicationScene: CPTemplateApplicationScene,
        didDisconnectInterfaceController interfaceController: CPInterfaceController
    ) {
        self.interfaceController = nil
        client.disconnect()
    }

    // MARK: - UI Templates

    private func buildRootTemplate() -> CPListTemplate {
        let quickActionsSection = CPListSection(
            items: [
                buildListItem(title: "🏠 Smart Home", detail: "Control lights, thermostat, locks"),
                buildListItem(title: "📊 Status Check", detail: "Get system status overview"),
                buildListItem(title: "🎤 Talk to Vera", detail: "Start voice conversation")
            ],
            header: "Quick Actions",
            sectionIndexTitle: nil
        )

        let recentSection = CPListSection(
            items: recentMessageItems(),
            header: "Recent",
            sectionIndexTitle: nil
        )

        let template = CPListTemplate(
            title: "eVera",
            sections: [quickActionsSection, recentSection]
        )
        template.tabTitle = "eVera"
        return template
    }

    private func buildListItem(title: String, detail: String) -> CPListItem {
        let item = CPListItem(text: title, detailText: detail)
        item.handler = { [weak self] _, completion in
            self?.handleQuickAction(title: title)
            completion()
        }
        return item
    }

    private func recentMessageItems() -> [CPListItem] {
        let recent = messages.suffix(5)
        if recent.isEmpty {
            return [CPListItem(text: "No messages yet", detailText: "Tap 'Talk to Vera' to start")]
        }
        return recent.map { msg in
            let prefix = msg.role == "user" ? "You" : "Vera"
            let truncated = msg.content.prefix(80)
            return CPListItem(text: "\(prefix): \(truncated)", detailText: nil)
        }
    }

    // MARK: - Actions

    private func handleQuickAction(title: String) {
        switch title {
        case let t where t.contains("Smart Home"):
            client.sendTranscript("What's the status of my smart home devices?")
        case let t where t.contains("Status"):
            client.sendTranscript("Give me a system status overview")
        case let t where t.contains("Talk"):
            startVoiceInput()
        default:
            break
        }
    }

    private func startVoiceInput() {
        let voiceTemplate = CPVoiceControlTemplate(voiceControlStates: [
            CPVoiceControlState(
                identifier: "listening",
                titleVariants: ["Listening...", "Speak now"],
                image: nil,
                repeats: false
            ),
            CPVoiceControlState(
                identifier: "processing",
                titleVariants: ["Processing..."],
                image: nil,
                repeats: false
            )
        ])
        interfaceController?.pushTemplate(voiceTemplate, animated: true, completion: nil)
    }

    // MARK: - Response Handling

    private func handleResponse(_ response: String) {
        messages.append((role: "vera", content: response))
        if messages.count > 20 { messages.removeFirst() }

        DispatchQueue.main.async { [weak self] in
            self?.showResponseTemplate(response)
            self?.client.speak(response)
        }
    }

    private func showResponseTemplate(_ response: String) {
        let infoTemplate = CPInformationTemplate(
            title: "Vera",
            layout: .leading,
            items: [
                CPInformationItem(title: nil, detail: response)
            ],
            actions: [
                CPTextButton(title: "Reply", textStyle: .confirm) { [weak self] _ in
                    self?.startVoiceInput()
                },
                CPTextButton(title: "Done", textStyle: .cancel) { [weak self] _ in
                    self?.interfaceController?.popToRootTemplate(animated: true, completion: nil)
                }
            ]
        )
        interfaceController?.pushTemplate(infoTemplate, animated: true, completion: nil)
    }
}
