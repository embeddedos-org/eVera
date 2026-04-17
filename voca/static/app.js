/* === Voca Web UI — Client Application === */

(function () {
    "use strict";

    // --- State ---
    const state = {
        ws: null,
        connected: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 10,
        reconnectDelay: 1000,
        startTime: Date.now(),
        messageCount: 0,
        ttsEnabled: true,
        agentUsage: {},
        tierUsage: { 0: 0, 1: 0, 2: 0, 3: 0 },
        statusPollInterval: null,
        eventSource: null,
        listenMode: "always",
    };

    // Mood → Face expression mapping
    const MOOD_TO_EXPRESSION = {
        happy: "happy",
        thinking: "thinking",
        excited: "excited",
        neutral: "idle",
        empathetic: "sad",
        error: "error",
    };

    // --- DOM Elements ---
    const dom = {
        chatMessages: document.getElementById("chatMessages"),
        chatInput: document.getElementById("chatInput"),
        sendBtn: document.getElementById("sendBtn"),
        micBtn: document.getElementById("micBtn"),
        ttsBtn: document.getElementById("ttsBtn"),
        typingIndicator: document.getElementById("typingIndicator"),
        connectionBadge: document.getElementById("connectionBadge"),
        toggleDashboard: document.getElementById("toggleDashboard"),
        dashboardPanel: document.getElementById("dashboardPanel"),
        statConnection: document.getElementById("statConnection"),
        statUptime: document.getElementById("statUptime"),
        statMessages: document.getElementById("statMessages"),
        agentUsageBody: document.getElementById("agentUsageBody"),
        tierBar0: document.getElementById("tierBar0"),
        tierBar1: document.getElementById("tierBar1"),
        tierBar2: document.getElementById("tierBar2"),
        tierBar3: document.getElementById("tierBar3"),
        tierCount0: document.getElementById("tierCount0"),
        tierCount1: document.getElementById("tierCount1"),
        tierCount2: document.getElementById("tierCount2"),
        tierCount3: document.getElementById("tierCount3"),
        memWorking: document.getElementById("memWorking"),
        memEpisodic: document.getElementById("memEpisodic"),
        memFacts: document.getElementById("memFacts"),
        factsList: document.getElementById("factsList"),
        eventLog: document.getElementById("eventLog"),
        listenModeSelector: document.getElementById("listenModeSelector"),
    };

    // --- WebSocket Connection ---

    function connectWebSocket() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${location.host}/ws`;

        state.ws = new WebSocket(wsUrl);

        state.ws.onopen = function () {
            state.connected = true;
            state.reconnectAttempts = 0;
            updateConnectionStatus("connected");
        };

        state.ws.onmessage = function (event) {
            try {
                const msg = JSON.parse(event.data);
                handleMessage(msg);
            } catch (e) {
                console.error("Failed to parse message:", e);
            }
        };

        state.ws.onclose = function () {
            state.connected = false;
            updateConnectionStatus("disconnected");
            scheduleReconnect();
        };

        state.ws.onerror = function () {
            state.connected = false;
            updateConnectionStatus("error");
        };
    }

    function scheduleReconnect() {
        if (state.reconnectAttempts >= state.maxReconnectAttempts) {
            updateConnectionStatus("error");
            return;
        }
        state.reconnectAttempts++;
        const delay = state.reconnectDelay * Math.min(state.reconnectAttempts, 5);
        setTimeout(connectWebSocket, delay);
    }

    function updateConnectionStatus(status) {
        const badge = dom.connectionBadge;
        badge.className = "connection-badge " + status;
        const label = badge.querySelector(".label");

        const labels = {
            connected: "Connected",
            disconnected: "Reconnecting…",
            error: "Disconnected",
        };
        label.textContent = labels[status] || "Unknown";
        dom.statConnection.textContent = labels[status] || "—";
    }

    // --- Message Handling ---

    function sendMessage(text) {
        if (!text.trim() || !state.connected) return;

        appendMessage("user", text);
        dom.chatInput.value = "";
        showTyping(true);
        VocaFace.setExpression("thinking");
        VocaWaveform.setColor("thinking");

        state.ws.send(JSON.stringify({
            type: "transcript",
            data: text,
        }));
    }

    function handleMessage(msg) {
        if (msg.type === "response") {
            showTyping(false);
            appendMessage("assistant", msg.response, {
                agent: msg.agent,
                tier: msg.tier,
                intent: msg.intent,
            });

            state.messageCount++;
            dom.statMessages.textContent = state.messageCount;

            // Track agent & tier usage
            state.agentUsage[msg.agent] = (state.agentUsage[msg.agent] || 0) + 1;
            state.tierUsage[msg.tier] = (state.tierUsage[msg.tier] || 0) + 1;
            updateAgentUsage();
            updateTierUsage();

            // Drive face expression from mood
            const mood = msg.mood || "neutral";
            const expression = MOOD_TO_EXPRESSION[mood] || "idle";
            VocaFace.setExpression(expression);
            VocaWaveform.setColor(expression);

            // Reset face to idle after a delay
            setTimeout(() => {
                if (VocaFace.getExpression() === expression) {
                    VocaFace.setExpression(VocaListener.isActive() ? "listening" : "idle");
                    VocaWaveform.setColor(VocaListener.isActive() ? "listening" : "idle");
                }
            }, 4000);

            // TTS
            if (state.ttsEnabled && msg.response) {
                speak(msg.response);
            }
        } else if (msg.type === "status") {
            updateDashboardFromStatus(msg);
        } else if (msg.type === "pong") {
            // heartbeat
        } else if (msg.type === "error") {
            showTyping(false);
            appendMessage("assistant", `⚠ Error: ${msg.message}`, { agent: "system", tier: 0 });
            VocaFace.setExpression("error");
            VocaWaveform.setColor("error");
            setTimeout(() => {
                VocaFace.setExpression("idle");
                VocaWaveform.setColor("idle");
            }, 3000);
        }
    }

    function appendMessage(role, text, meta) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}`;

        // Header
        const header = document.createElement("div");
        header.className = "message-header";

        if (role === "user") {
            header.textContent = "👤 You";
        } else if (meta) {
            const label = document.createElement("span");
            label.textContent = "🤖 ";

            const badge = document.createElement("span");
            badge.className = `agent-badge tier-${meta.tier}`;
            badge.textContent = `${meta.agent}|T${meta.tier}`;

            if (meta.tier === 0) {
                const bolt = document.createElement("span");
                bolt.className = "tier-bolt";
                bolt.textContent = " ⚡";
                badge.appendChild(bolt);
            }

            header.appendChild(label);
            header.appendChild(badge);
        }

        // Bubble
        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.textContent = text;

        // Time
        const timeEl = document.createElement("div");
        timeEl.className = "message-time";
        timeEl.textContent = formatTime(new Date());

        msgDiv.appendChild(header);
        msgDiv.appendChild(bubble);
        msgDiv.appendChild(timeEl);

        dom.chatMessages.appendChild(msgDiv);
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }

    function showTyping(show) {
        dom.typingIndicator.hidden = !show;
        if (show) {
            dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
        }
    }

    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    // --- Web Speech API: Synthesis ---

    function speak(text) {
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();

        VocaFace.setExpression("speaking");
        VocaWaveform.setColor("speaking");

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onboundary = function () {
            VocaFace.setSpeakAmplitude(0.6 + Math.random() * 0.4);
        };

        utterance.onend = function () {
            VocaFace.setSpeakAmplitude(0);
            VocaFace.setExpression(VocaListener.isActive() ? "listening" : "idle");
            VocaWaveform.setColor(VocaListener.isActive() ? "listening" : "idle");
        };

        window.speechSynthesis.speak(utterance);
    }

    function toggleTts() {
        state.ttsEnabled = !state.ttsEnabled;
        dom.ttsBtn.classList.toggle("active", state.ttsEnabled);
        dom.ttsBtn.querySelector(".tts-icon").textContent = state.ttsEnabled ? "🔊" : "🔇";

        if (!state.ttsEnabled) {
            window.speechSynthesis && window.speechSynthesis.cancel();
        }
    }

    // --- Listener Integration ---

    function initListener() {
        const supported = VocaListener.init({
            onTranscript: function (text) {
                sendMessage(text);
            },
            onStateChange: function (listenerState) {
                if (listenerState === "listening" || listenerState === "wake_listening") {
                    VocaFace.setExpression("listening");
                    VocaWaveform.setColor("listening");
                    dom.micBtn.classList.add("active");
                } else {
                    if (VocaFace.getExpression() === "listening") {
                        VocaFace.setExpression("idle");
                        VocaWaveform.setColor("idle");
                    }
                    dom.micBtn.classList.remove("active");
                }
            },
            onWakeWord: function () {
                VocaFace.setExpression("excited");
                setTimeout(() => VocaFace.setExpression("listening"), 800);
            },
            onMicStream: function (stream) {
                VocaWaveform.connectMic(stream);
            },
        });

        if (!supported) {
            dom.micBtn.title = "Speech recognition not supported";
            dom.micBtn.style.opacity = "0.4";
            dom.micBtn.style.cursor = "not-allowed";
            dom.listenModeSelector.style.display = "none";
        } else {
            // Auto-start in always-on mode
            VocaListener.setMode("always");
        }
    }

    function initModeSelector() {
        const buttons = dom.listenModeSelector.querySelectorAll(".mode-btn");
        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                const mode = btn.dataset.mode;
                state.listenMode = mode;
                buttons.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                VocaListener.setMode(mode);
            });
        });
    }

    // --- Dashboard Updates ---

    function startStatusPolling() {
        fetchStatus();
        state.statusPollInterval = setInterval(fetchStatus, 5000);
    }

    async function fetchStatus() {
        try {
            const res = await fetch("/status");
            const data = await res.json();
            updateDashboardFromStatus(data);
        } catch (e) {
            // Status endpoint unavailable
        }
    }

    function updateDashboardFromStatus(data) {
        if (data.memory) {
            dom.memWorking.textContent = `${data.memory.working_turns || 0} turns`;
            dom.memEpisodic.textContent = data.memory.episodic_events || 0;
            dom.memFacts.textContent = data.memory.semantic_facts || 0;
        }

        if (data.memory_facts) {
            renderFacts(data.memory_facts);
        }
    }

    function updateAgentUsage() {
        const entries = Object.entries(state.agentUsage).sort((a, b) => b[1] - a[1]);
        const maxCount = entries.length > 0 ? entries[0][1] : 1;

        if (entries.length === 0) {
            dom.agentUsageBody.innerHTML = '<div class="placeholder-text">No activity yet</div>';
            return;
        }

        dom.agentUsageBody.innerHTML = entries.map(([name, count]) => {
            const pct = Math.round((count / maxCount) * 100);
            return `
                <div class="agent-row">
                    <span class="agent-name">${escapeHtml(name)}</span>
                    <div class="agent-bar-track">
                        <div class="agent-bar-fill" style="width:${pct}%"></div>
                    </div>
                    <span class="agent-count">${count}</span>
                </div>
            `;
        }).join("");
    }

    function updateTierUsage() {
        const total = Object.values(state.tierUsage).reduce((s, v) => s + v, 0) || 1;

        for (let t = 0; t <= 3; t++) {
            const count = state.tierUsage[t] || 0;
            const pct = Math.round((count / total) * 100);
            const bar = dom[`tierBar${t}`];
            const countEl = dom[`tierCount${t}`];
            if (bar) bar.style.width = pct + "%";
            if (countEl) countEl.textContent = count;
        }
    }

    function renderFacts(facts) {
        const entries = Object.entries(facts);
        if (entries.length === 0) {
            dom.factsList.innerHTML = "";
            return;
        }

        dom.factsList.innerHTML = entries.map(([k, v]) =>
            `<div class="fact-row">
                <span class="fact-key">${escapeHtml(k)}:</span>
                <span class="fact-value">${escapeHtml(v)}</span>
            </div>`
        ).join("");
    }

    // --- Uptime Timer ---

    function updateUptime() {
        const elapsed = Date.now() - state.startTime;
        const seconds = Math.floor(elapsed / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        let uptimeStr;
        if (hours > 0) {
            uptimeStr = `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            uptimeStr = `${minutes}m ${seconds % 60}s`;
        } else {
            uptimeStr = `${seconds}s`;
        }

        dom.statUptime.textContent = uptimeStr;
    }

    // --- SSE Event Log ---

    function connectEventStream() {
        state.eventSource = new EventSource("/events/stream");

        state.eventSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);
                appendEventLog(data);
            } catch (e) {
                // skip
            }
        };

        state.eventSource.onerror = function () {
            // EventSource auto-reconnects
        };
    }

    function appendEventLog(event) {
        const placeholder = dom.eventLog.querySelector(".placeholder-text");
        if (placeholder) placeholder.remove();

        const row = document.createElement("div");
        row.className = "event-row";

        const ts = event.timestamp ? new Date(event.timestamp * 1000) : new Date();
        const timeStr = ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

        const eventType = (event.type || "").toUpperCase().replace(/_/g, " ");
        const dataStr = event.data ? JSON.stringify(event.data) : "";

        row.innerHTML = `
            <span class="event-time">${timeStr}</span>
            <span class="event-type">${escapeHtml(eventType)}</span>
            <span class="event-data" title="${escapeHtml(dataStr)}">${escapeHtml(dataStr.substring(0, 80))}</span>
        `;

        dom.eventLog.appendChild(row);

        while (dom.eventLog.children.length > 50) {
            dom.eventLog.removeChild(dom.eventLog.firstChild);
        }

        dom.eventLog.scrollTop = dom.eventLog.scrollHeight;
    }

    // --- Heartbeat ---

    function startHeartbeat() {
        setInterval(function () {
            if (state.connected && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    }

    // --- Waveform-to-Face amplitude sync ---

    function startAmplitudeSync() {
        setInterval(function () {
            if (VocaFace.getExpression() === "speaking") return;
            const amp = VocaWaveform.getAmplitude();
            if (amp > 0.01) {
                VocaFace.setSpeakAmplitude(amp * 2);
            }
        }, 50);
    }

    // --- Utility ---

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // --- Event Listeners ---

    dom.sendBtn.addEventListener("click", function () {
        sendMessage(dom.chatInput.value);
    });

    dom.chatInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage(dom.chatInput.value);
        }
    });

    dom.micBtn.addEventListener("click", function () {
        VocaListener.toggle();
    });

    dom.ttsBtn.addEventListener("click", toggleTts);

    dom.toggleDashboard.addEventListener("click", function () {
        dom.dashboardPanel.classList.toggle("collapsed");
        const collapsed = dom.dashboardPanel.classList.contains("collapsed");
        dom.toggleDashboard.textContent = collapsed ? "▶" : "◀";
    });

    // --- Initialize ---

    VocaFace.init("faceCanvas", "faceGlowRing");
    VocaWaveform.init("waveformCanvas");
    initListener();
    initModeSelector();
    connectWebSocket();
    startStatusPolling();
    startHeartbeat();
    connectEventStream();
    startAmplitudeSync();
    setInterval(updateUptime, 1000);

    // Set initial TTS button state
    dom.ttsBtn.classList.add("active");
})();
