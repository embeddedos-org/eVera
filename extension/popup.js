/**
 * eVera Chrome Extension — Popup
 */

(function () {
    "use strict";

    const statusDot = document.getElementById("statusDot");
    const statusText = document.getElementById("statusText");

    // Check status
    chrome.runtime.sendMessage({ type: "get-status" }, (response) => {
        if (response && response.connected) {
            statusDot.className = "dot connected";
            statusText.textContent = `Connected to ${response.serverUrl}`;
        } else {
            statusDot.className = "dot error";
            statusText.textContent = "Disconnected";
        }
    });

    // Open side panel
    document.getElementById("openSidePanel").addEventListener("click", async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab) {
            chrome.sidePanel.open({ tabId: tab.id });
        }
        window.close();
    });

    // Reconnect
    document.getElementById("reconnectBtn").addEventListener("click", () => {
        chrome.runtime.sendMessage({ type: "reconnect" });
        statusDot.className = "dot";
        statusText.textContent = "Reconnecting...";
        setTimeout(() => {
            chrome.runtime.sendMessage({ type: "get-status" }, (response) => {
                if (response && response.connected) {
                    statusDot.className = "dot connected";
                    statusText.textContent = "Connected";
                } else {
                    statusDot.className = "dot error";
                    statusText.textContent = "Still disconnected";
                }
            });
        }, 3000);
    });

    // Settings
    document.getElementById("settingsBtn").addEventListener("click", () => {
        chrome.runtime.openOptionsPage();
        window.close();
    });
})();
