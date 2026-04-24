/**
 * eVera Chrome Extension — Background Service Worker
 *
 * Handles: WebSocket to backend, context menus, message routing, connection badge.
 */

const DEFAULT_SERVER_URL = "http://localhost:8000";
let ws = null;
let serverUrl = DEFAULT_SERVER_URL;
let connected = false;

// --- Initialization ---
chrome.runtime.onInstalled.addListener(() => {
    // Create context menu items
    chrome.contextMenus.create({
        id: "vera-ask",
        title: "Ask eVera",
        contexts: ["selection"],
    });
    chrome.contextMenus.create({
        id: "vera-summarize",
        title: "Summarize with eVera",
        contexts: ["selection"],
    });
    chrome.contextMenus.create({
        id: "vera-translate",
        title: "Translate with eVera",
        contexts: ["selection"],
    });
    chrome.contextMenus.create({
        id: "vera-explain",
        title: "Explain with eVera",
        contexts: ["selection"],
    });
    chrome.contextMenus.create({
        id: "vera-grammar",
        title: "Fix Grammar",
        contexts: ["selection"],
    });

    // Load saved server URL
    chrome.storage.sync.get(["serverUrl"], (result) => {
        if (result.serverUrl) {
            serverUrl = result.serverUrl;
        }
        connectWebSocket();
    });
});

// --- WebSocket Connection ---
function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const wsUrl = serverUrl.replace("http://", "ws://").replace("https://", "wss://") + "/ws";

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            connected = true;
            updateBadge("connected");
            console.log("[eVera] WebSocket connected");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                // Forward responses to sidepanel
                chrome.runtime.sendMessage({ type: "ws-message", data: msg }).catch(() => {});
            } catch (e) {
                console.error("[eVera] Failed to parse WS message:", e);
            }
        };

        ws.onclose = () => {
            connected = false;
            updateBadge("disconnected");
            console.log("[eVera] WebSocket disconnected — reconnecting in 5s...");
            setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (err) => {
            console.error("[eVera] WebSocket error:", err);
            connected = false;
            updateBadge("error");
        };
    } catch (e) {
        console.error("[eVera] WebSocket connection failed:", e);
        connected = false;
        updateBadge("error");
        setTimeout(connectWebSocket, 5000);
    }
}

function updateBadge(status) {
    const colors = {
        connected: "#4ade80",
        disconnected: "#6b7280",
        error: "#ef4444",
    };

    chrome.action.setBadgeBackgroundColor({ color: colors[status] || "#6b7280" });
    chrome.action.setBadgeText({ text: status === "connected" ? "" : "!" });
}

// --- Context Menu Handlers ---
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    const selectedText = info.selectionText;
    if (!selectedText) return;

    const actionMap = {
        "vera-ask": "chat",
        "vera-summarize": "summarize",
        "vera-translate": "translate",
        "vera-explain": "explain",
        "vera-grammar": "grammar",
    };

    const action = actionMap[info.menuItemId];
    if (!action) return;

    if (action === "chat") {
        // Send via WebSocket
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "transcript", data: selectedText }));
        }
        // Open side panel
        chrome.sidePanel.open({ tabId: tab.id });
    } else {
        // Use REST endpoint
        try {
            const response = await fetch(`${serverUrl}/extension/${action}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: selectedText }),
            });
            const result = await response.json();

            // Send result to content script for inline display
            chrome.tabs.sendMessage(tab.id, {
                type: "vera-result",
                action: action,
                result: result.result,
            });
        } catch (e) {
            console.error("[eVera] Extension action failed:", e);
            chrome.tabs.sendMessage(tab.id, {
                type: "vera-result",
                action: action,
                result: "Error: Could not reach eVera backend. Is it running?",
            });
        }
    }
});

// --- Message Handlers ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "get-status") {
        sendResponse({ connected, serverUrl });
        return true;
    }

    if (message.type === "send-chat") {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "transcript", data: message.text }));
            sendResponse({ sent: true });
        } else {
            sendResponse({ sent: false, error: "Not connected" });
        }
        return true;
    }

    if (message.type === "update-server-url") {
        serverUrl = message.url;
        chrome.storage.sync.set({ serverUrl: message.url });
        if (ws) ws.close();
        connectWebSocket();
        sendResponse({ ok: true });
        return true;
    }

    if (message.type === "reconnect") {
        if (ws) ws.close();
        connectWebSocket();
        sendResponse({ ok: true });
        return true;
    }
});

// --- Side Panel ---
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});

// Keep service worker alive
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
    }
}, 25000);
