/* === Voca Web UI — Client Application (Glassmorphism Edition) === */

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
        agentEventSource: null,
        listenMode: "always",
        currentAgentView: "cards",
    };

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
        toggleAgentPanel: document.getElementById("toggleAgentPanel"),
        agentPanel: document.getElementById("agentPanel"),
        agentViewContainer: document.getElementById("agentViewContainer"),
        viewSwitcher: document.getElementById("viewSwitcher"),
        statConnection: document.getElementById("statConnection"),
        statUptime: document.getElementById("statUptime"),
        statMessages: document.getElementById("statMessages"),
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
        langSelector: document.getElementById("langSelector"),
        expressionLabel: document.getElementById("expressionLabel"),
        particleField: document.getElementById("particleField"),
    };

    // --- Particle Background ---

    function initParticles() {
        const field = dom.particleField;
        if (!field) return;
        const count = 20;
        for (let i = 0; i < count; i++) {
            const p = document.createElement("div");
            p.className = "particle";
            p.style.left = Math.random() * 100 + "%";
            p.style.animationDuration = (8 + Math.random() * 12) + "s";
            p.style.animationDelay = (Math.random() * 10) + "s";
            p.style.width = p.style.height = (2 + Math.random() * 3) + "px";
            p.style.opacity = (0.15 + Math.random() * 0.3).toString();
            field.appendChild(p);
        }
    }

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
        if (dom.statConnection) {
            dom.statConnection.textContent = labels[status] || "—";
        }
    }

    // --- Message Handling ---

    function sendMessage(text) {
        if (!text.trim() || !state.connected) return;

        appendMessage("user", text);
        dom.chatInput.value = "";
        showTyping(true);
        setExpression("thinking");

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
            if (dom.statMessages) dom.statMessages.textContent = state.messageCount;

            state.agentUsage[msg.agent] = (state.agentUsage[msg.agent] || 0) + 1;
            state.tierUsage[msg.tier] = (state.tierUsage[msg.tier] || 0) + 1;
            updateTierUsage();

            const mood = msg.mood || "neutral";
            const expression = MOOD_TO_EXPRESSION[mood] || "idle";
            setExpression(expression);

            setTimeout(() => {
                if (typeof VocaFace !== "undefined" && VocaFace.getExpression() === expression) {
                    const nextExpr = (typeof VocaListener !== "undefined" && VocaListener.isActive()) ? "listening" : "idle";
                    setExpression(nextExpr);
                }
            }, 4000);

            if (state.ttsEnabled && msg.response) {
                speak(msg.response);
            }

            // Update agent view with response info
            if (typeof VocaAgentsView !== "undefined") {
                VocaAgentsView.agentDone(msg.agent, msg.response);
            }
        } else if (msg.type === "status") {
            updateDashboardFromStatus(msg);
        } else if (msg.type === "pong") {
            // heartbeat
        } else if (msg.type === "error") {
            showTyping(false);
            appendMessage("assistant", `⚠ Error: ${msg.message}`, { agent: "system", tier: 0 });
            setExpression("error");
            setTimeout(() => setExpression("idle"), 3000);
        }
    }

    function setExpression(expr) {
        if (typeof VocaFace !== "undefined") {
            VocaFace.setExpression(expr);
        }
        if (typeof VocaWaveform !== "undefined") {
            VocaWaveform.setColor(expr);
        }
        if (dom.expressionLabel) {
            dom.expressionLabel.textContent = expr;
        }
    }

    function appendMessage(role, text, meta) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}`;

        const header = document.createElement("div");
        header.className = "message-header";

        if (role === "user") {
            header.textContent = "👤 You";
        } else if (meta) {
            const label = document.createElement("span");
            label.textContent = "🤖 ";

            const badge = document.createElement("span");
            badge.className = `agent-badge tier-${meta.tier}`;
            badge.textContent = `${meta.agent} · T${meta.tier}`;

            if (meta.tier === 0) {
                const bolt = document.createElement("span");
                bolt.className = "tier-bolt";
                bolt.textContent = " ⚡";
                badge.appendChild(bolt);
            }

            header.appendChild(label);
            header.appendChild(badge);
        }

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.textContent = text;

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

        setExpression("speaking");

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onboundary = function () {
            if (typeof VocaFace !== "undefined") {
                VocaFace.setSpeakAmplitude(0.6 + Math.random() * 0.4);
            }
        };

        utterance.onend = function () {
            if (typeof VocaFace !== "undefined") {
                VocaFace.setSpeakAmplitude(0);
            }
            const nextExpr = (typeof VocaListener !== "undefined" && VocaListener.isActive()) ? "listening" : "idle";
            setExpression(nextExpr);
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
        if (typeof VocaListener === "undefined") return;

        const supported = VocaListener.init({
            onTranscript: function (text) {
                sendMessage(text);
            },
            onStateChange: function (listenerState) {
                if (listenerState === "listening" || listenerState === "wake_listening") {
                    setExpression("listening");
                    dom.micBtn.classList.add("active");
                } else {
                    if (typeof VocaFace !== "undefined" && VocaFace.getExpression() === "listening") {
                        setExpression("idle");
                    }
                    dom.micBtn.classList.remove("active");
                }
            },
            onWakeWord: function () {
                setExpression("excited");
                setTimeout(() => setExpression("listening"), 800);
            },
            onMicStream: function (stream) {
                if (typeof VocaWaveform !== "undefined") {
                    VocaWaveform.connectMic(stream);
                }
            },
        });

        if (!supported) {
            dom.micBtn.title = "Speech recognition not supported";
            dom.micBtn.style.opacity = "0.4";
            dom.micBtn.style.cursor = "not-allowed";
            dom.listenModeSelector.style.display = "none";
        } else {
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
                if (typeof VocaListener !== "undefined") {
                    VocaListener.setMode(mode);
                }
            });
        });
    }

    function initLanguageSelector() {
        if (dom.langSelector) {
            dom.langSelector.addEventListener("change", function () {
                if (typeof VocaListener !== "undefined") {
                    VocaListener.setLanguage(dom.langSelector.value);
                }
            });
        }
    }

    // --- View Switcher ---

    function initViewSwitcher() {
        if (!dom.viewSwitcher) return;
        const buttons = dom.viewSwitcher.querySelectorAll(".view-btn");
        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                const view = btn.dataset.view;
                state.currentAgentView = view;
                buttons.forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                if (typeof VocaAgentsView !== "undefined") {
                    VocaAgentsView.switchView(view);
                }
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
            if (dom.memWorking) dom.memWorking.textContent = `${data.memory.working_turns || 0} turns`;
            if (dom.memEpisodic) dom.memEpisodic.textContent = data.memory.episodic_events || 0;
            if (dom.memFacts) dom.memFacts.textContent = data.memory.semantic_facts || 0;
        }

        if (data.memory_facts) {
            renderFacts(data.memory_facts);
        }
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
        if (!dom.factsList) return;
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

        if (dom.statUptime) dom.statUptime.textContent = uptimeStr;
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
        if (!dom.eventLog) return;
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
            <span class="event-data" title="${escapeHtml(dataStr)}">${escapeHtml(dataStr.substring(0, 60))}</span>
        `;

        dom.eventLog.appendChild(row);

        while (dom.eventLog.children.length > 50) {
            dom.eventLog.removeChild(dom.eventLog.firstChild);
        }

        dom.eventLog.scrollTop = dom.eventLog.scrollHeight;
    }

    // --- Agent Status SSE ---

    function connectAgentStream() {
        try {
            state.agentEventSource = new EventSource("/agents/stream");

            state.agentEventSource.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (typeof VocaAgentsView !== "undefined") {
                        VocaAgentsView.handleAgentEvent(data);
                    }
                } catch (e) {
                    // skip malformed events
                }
            };

            state.agentEventSource.onerror = function () {
                // Will auto-reconnect, or endpoint doesn't exist yet
            };
        } catch (e) {
            // Agent stream not available
        }
    }

    // --- Heartbeat ---

    function startHeartbeat() {
        setInterval(function () {
            if (state.connected && state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    }

    // --- Waveform-to-Face amplitude sync ---

    function startAmplitudeSync() {
        setInterval(function () {
            if (typeof VocaFace === "undefined" || typeof VocaWaveform === "undefined") return;
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

    // --- PWA Service Worker ---

    function registerServiceWorker() {
        if ("serviceWorker" in navigator) {
            navigator.serviceWorker.register("/static/sw.js").catch(function () {
                // SW registration failed — not critical
            });
        }
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
        if (typeof VocaListener !== "undefined") {
            VocaListener.toggle();
        }
    });

    dom.ttsBtn.addEventListener("click", toggleTts);

    if (dom.toggleAgentPanel) {
        dom.toggleAgentPanel.addEventListener("click", function () {
            dom.agentPanel.classList.toggle("collapsed");
            const collapsed = dom.agentPanel.classList.contains("collapsed");
            dom.toggleAgentPanel.textContent = collapsed ? "▶" : "◀";
        });
    }

    // --- Initialize ---

    initParticles();

    if (typeof VocaFace !== "undefined") {
        VocaFace.init("faceCanvas", "faceGlowRing");
    }
    if (typeof VocaWaveform !== "undefined") {
        VocaWaveform.init("waveformCanvas");
    }

    initListener();
    initModeSelector();
    initLanguageSelector();
    initViewSwitcher();
    connectWebSocket();
    startStatusPolling();
    startHeartbeat();
    connectEventStream();
    connectAgentStream();
    startAmplitudeSync();
    registerServiceWorker();
    setInterval(updateUptime, 1000);
})();
