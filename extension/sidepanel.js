/**
 * eVera Chrome Extension — Side Panel Chat
 */

(function () {
    "use strict";

    const chatArea = document.getElementById("chatArea");
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const statusDot = document.getElementById("statusDot");

    let connected = false;

    // --- Check connection status ---
    function checkStatus() {
        chrome.runtime.sendMessage({ type: "get-status" }, (response) => {
            if (response) {
                connected = response.connected;
                statusDot.className = "status" + (connected ? " connected" : "");
            }
        });
    }

    setInterval(checkStatus, 3000);
    checkStatus();

    // --- Send message ---
    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        addMessage(text, "user");
        chatInput.value = "";

        chrome.runtime.sendMessage({ type: "send-chat", text }, (response) => {
            if (!response || !response.sent) {
                addMessage("⚠️ Not connected to eVera backend.", "bot");
            }
        });
    }

    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // --- Receive messages from background ---
    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === "ws-message" && message.data) {
            const data = message.data;
            if (data.type === "response") {
                addMessage(data.response, "bot", data.agent, data.tier);
            } else if (data.type === "stream_token") {
                appendToLastBot(data.content);
            } else if (data.type === "stream_end") {
                // Streaming complete
            }
        }
    });

    // --- UI helpers ---
    function addMessage(text, type, agent, tier) {
        const msg = document.createElement("div");
        msg.className = `msg ${type}`;
        msg.textContent = text;

        if (agent) {
            const meta = document.createElement("div");
            meta.className = "meta";
            meta.textContent = `${agent}${tier !== undefined ? ` • T${tier}` : ""}`;
            msg.appendChild(meta);
        }

        chatArea.appendChild(msg);
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function appendToLastBot(content) {
        const msgs = chatArea.querySelectorAll(".msg.bot");
        if (msgs.length > 0) {
            const last = msgs[msgs.length - 1];
            last.textContent += content;
            chatArea.scrollTop = chatArea.scrollHeight;
        } else {
            addMessage(content, "bot");
        }
    }

    // Welcome message
    addMessage("👋 Hi! I'm eVera. Select text on any page for quick AI actions, or chat with me here.", "bot");
})();
