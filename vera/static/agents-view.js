/* === Vera Agents View — Live Agent Visualization === */

var VeraAgentsView = (function () {
    "use strict";

    let container = null;
    let currentView = "cards";
    let agents = {};
    let timeline = [];
    let constellationCanvas = null;
    let constellationCtx = null;
    let constellationAnimId = null;

    const AGENT_ICONS = {
        companion: "💬",
        operator: "🖥️",
        browser: "🌐",
        researcher: "🔍",
        writer: "✍️",
        life_manager: "📅",
        home_controller: "🏠",
        income: "💰",
        coder: "💻",
        brokers: "📈",
        git_agent: "🔧",
        vision: "👁️",
        scheduler: "⏰",
        system: "⚙️",
    };

    const AGENT_COLORS = {
        companion: "#6c7bff",
        operator: "#60a5fa",
        researcher: "#4ade80",
        writer: "#f59e0b",
        browser: "#a78bfa",
        life_manager: "#f43f5e",
        home_controller: "#14b8a6",
        income: "#eab308",
        coder: "#ec4899",
        brokers: "#f97316",
        git_agent: "#8b5cf6",
        vision: "#06b6d4",
    };

    function init() {
        container = document.getElementById("agentViewContainer");
    }

    function switchView(view) {
        currentView = view;
        if (constellationAnimId) {
            cancelAnimationFrame(constellationAnimId);
            constellationAnimId = null;
        }
        render();
    }

    function handleAgentEvent(event) {
        // Route pipeline events to pipeline view
        if (event.type === "pipeline") {
            if (typeof VeraPipelineView !== "undefined") {
                VeraPipelineView.handlePipelineEvent(event);
            }
            return;
        }

        const name = event.agent || "unknown";
        const status = event.status || "idle";

        if (!agents[name]) {
            agents[name] = {
                name: name,
                status: "idle",
                tool: null,
                args: null,
                progress: 0,
                result: null,
                startTime: null,
                connections: [],
            };
        }

        const agent = agents[name];
        agent.status = status;

        if (event.tool) {
            agent.tool = event.tool;
            agent.args = event.args || {};
        }
        if (event.progress !== undefined) {
            agent.progress = event.progress;
        }
        if (event.result) {
            agent.result = event.result;
        }
        if (status === "working" && !agent.startTime) {
            agent.startTime = Date.now();
        }
        if (status === "done") {
            agent.progress = 1;
        }
        if (event.connections) {
            agent.connections = event.connections;
        }

        timeline.push({
            timestamp: new Date(),
            agent: name,
            status: status,
            tool: event.tool || null,
            result: event.result || null,
        });

        if (timeline.length > 100) {
            timeline = timeline.slice(-80);
        }

        render();
    }

    function agentDone(agentName, response) {
        if (!agents[agentName]) {
            agents[agentName] = {
                name: agentName,
                status: "done",
                tool: null,
                args: null,
                progress: 1,
                result: response ? response.substring(0, 80) : null,
                startTime: null,
                connections: [],
            };
        } else {
            agents[agentName].status = "done";
            agents[agentName].progress = 1;
            if (response) {
                agents[agentName].result = response.substring(0, 80);
            }
        }

        timeline.push({
            timestamp: new Date(),
            agent: agentName,
            status: "done",
            tool: null,
            result: response ? response.substring(0, 60) : null,
        });

        render();

        setTimeout(() => {
            if (agents[agentName] && agents[agentName].status === "done") {
                agents[agentName].status = "idle";
                render();
            }
        }, 5000);
    }

    function render() {
        if (!container) return;

        switch (currentView) {
            case "cards":
                renderCards();
                break;
            case "timeline":
                renderTimeline();
                break;
            case "graph":
                renderConstellation();
                break;
            case "pipeline":
                if (typeof VeraPipelineView !== "undefined") {
                    VeraPipelineView.render();
                }
                break;
        }
    }

    // --- Cards View ---

    function renderCards() {
        const entries = Object.entries(agents);
        if (entries.length === 0) {
            container.innerHTML = `
                <div class="agent-placeholder">
                    <span class="placeholder-icon">🤖</span>
                    <span>Agents will appear here when active…</span>
                </div>`;
            return;
        }

        const sorted = entries.sort((a, b) => {
            const order = { working: 0, idle: 1, done: 2 };
            return (order[a[1].status] || 1) - (order[b[1].status] || 1);
        });

        container.innerHTML = sorted.map(([name, agent]) => {
            const icon = AGENT_ICONS[name] || "🤖";
            const statusClass = agent.status;
            const pct = Math.round((agent.progress || 0) * 100);
            const taskText = agent.tool
                ? `${agent.tool}(${formatArgs(agent.args)})`
                : agent.result
                    ? truncate(agent.result, 50)
                    : "Waiting for input…";

            const statusLabel = agent.status === "working" ? "● Working"
                : agent.status === "done" ? "✓ Done"
                : "○ Idle";

            return `
                <div class="agent-card ${statusClass}">
                    <div class="agent-card-header">
                        <span class="agent-card-name">
                            ${icon} ${escapeHtml(capitalize(name))}
                        </span>
                        <span class="agent-status-dot ${statusClass}"></span>
                    </div>
                    <div class="agent-card-task">${escapeHtml(taskText)}</div>
                    ${agent.status === "working" ? `
                        <div class="agent-progress">
                            <div class="agent-progress-fill" style="width:${pct}%"></div>
                        </div>` : ""}
                </div>`;
        }).join("");
    }

    // --- Timeline View ---

    function renderTimeline() {
        if (timeline.length === 0) {
            container.innerHTML = `
                <div class="agent-placeholder">
                    <span class="placeholder-icon">📋</span>
                    <span>Agent activity timeline will appear here…</span>
                </div>`;
            return;
        }

        const recent = timeline.slice(-30).reverse();

        container.innerHTML = recent.map((entry, i) => {
            const icon = AGENT_ICONS[entry.agent] || "🤖";
            const timeStr = entry.timestamp.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });

            const action = entry.tool
                ? `Called ${entry.tool}`
                : entry.status === "done"
                    ? "Completed"
                    : entry.status === "working"
                        ? "Started working"
                        : "Status: " + entry.status;

            const resultPreview = entry.result ? truncate(entry.result, 40) : "";
            const isActive = entry.status === "working";
            const color = AGENT_COLORS[entry.agent] || "#6c7bff";

            return `
                <div class="timeline-entry" style="animation-delay:${i * 0.05}s">
                    <div class="timeline-dot ${isActive ? "active" : ""}" style="border-color:${color}; ${isActive ? `background:${color}` : ""}"></div>
                    <div class="timeline-body">
                        <div class="timeline-time">${timeStr}</div>
                        <div class="timeline-agent">${icon} ${escapeHtml(capitalize(entry.agent))}</div>
                        <div class="timeline-action">${escapeHtml(action)}${resultPreview ? " — " + escapeHtml(resultPreview) : ""}</div>
                    </div>
                </div>`;
        }).join("");
    }

    // --- Constellation View ---

    function renderConstellation() {
        const entries = Object.entries(agents);

        if (entries.length === 0) {
            container.innerHTML = `
                <div class="agent-placeholder">
                    <span class="placeholder-icon">✦</span>
                    <span>Agent constellation will appear here…</span>
                </div>`;
            return;
        }

        if (!constellationCanvas || !container.contains(constellationCanvas)) {
            container.innerHTML = "";
            constellationCanvas = document.createElement("canvas");
            constellationCanvas.className = "constellation-canvas";
            container.appendChild(constellationCanvas);
            constellationCtx = constellationCanvas.getContext("2d");
        }

        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        constellationCanvas.width = rect.width * dpr;
        constellationCanvas.height = rect.height * dpr;
        constellationCanvas.style.width = rect.width + "px";
        constellationCanvas.style.height = rect.height + "px";
        constellationCtx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const cx = w / 2;
        const cy = h / 2;
        const radius = Math.min(w, h) * 0.35;

        const nodes = entries.map(([name, agent], i) => {
            const angle = (i / entries.length) * Math.PI * 2 - Math.PI / 2;
            return {
                name: name,
                x: cx + Math.cos(angle) * radius,
                y: cy + Math.sin(angle) * radius,
                status: agent.status,
                color: AGENT_COLORS[name] || "#6c7bff",
                connections: agent.connections || [],
            };
        });

        function drawFrame() {
            const ctx = constellationCtx;
            ctx.clearRect(0, 0, w, h);

            // Draw connections
            nodes.forEach(node => {
                node.connections.forEach(targetName => {
                    const target = nodes.find(n => n.name === targetName);
                    if (!target) return;

                    ctx.beginPath();
                    ctx.moveTo(node.x, node.y);
                    ctx.lineTo(target.x, target.y);
                    ctx.strokeStyle = "rgba(108, 123, 255, 0.15)";
                    ctx.lineWidth = 1.5;
                    ctx.stroke();

                    // Animated particle along connection
                    const t = (Date.now() % 3000) / 3000;
                    const px = node.x + (target.x - node.x) * t;
                    const py = node.y + (target.y - node.y) * t;
                    ctx.beginPath();
                    ctx.arc(px, py, 2, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(108, 123, 255, 0.5)";
                    ctx.fill();
                });
            });

            // Draw nodes
            nodes.forEach(node => {
                const isActive = node.status === "working";
                const glowSize = isActive ? 20 + Math.sin(Date.now() * 0.003) * 5 : 10;

                // Glow
                const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, glowSize);
                gradient.addColorStop(0, node.color + (isActive ? "40" : "20"));
                gradient.addColorStop(1, "transparent");
                ctx.beginPath();
                ctx.arc(node.x, node.y, glowSize, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();

                // Circle
                const nodeRadius = isActive ? 18 : 14;
                ctx.beginPath();
                ctx.arc(node.x, node.y, nodeRadius, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(10, 14, 26, 0.9)";
                ctx.fill();
                ctx.strokeStyle = node.color + (isActive ? "cc" : "66");
                ctx.lineWidth = 2;
                ctx.stroke();

                // Icon
                const icon = AGENT_ICONS[node.name] || "🤖";
                ctx.font = "14px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(icon, node.x, node.y);

                // Label
                ctx.font = "10px -apple-system, sans-serif";
                ctx.fillStyle = isActive ? node.color : "rgba(139, 144, 176, 0.8)";
                ctx.fillText(capitalize(node.name), node.x, node.y + nodeRadius + 14);
            });

            constellationAnimId = requestAnimationFrame(drawFrame);
        }

        drawFrame();
    }

    // --- Helpers ---

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, " ");
    }

    function truncate(str, len) {
        if (!str) return "";
        return str.length > len ? str.substring(0, len) + "…" : str;
    }

    function formatArgs(args) {
        if (!args) return "";
        const entries = Object.entries(args);
        if (entries.length === 0) return "";
        return entries.map(([k, v]) => {
            const val = typeof v === "string" ? `"${truncate(v, 20)}"` : v;
            return `${k}=${val}`;
        }).join(", ");
    }

    // Init on load
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    return {
        switchView: switchView,
        handleAgentEvent: handleAgentEvent,
        agentDone: agentDone,
        getAgents: function () { return agents; },
    };
})();
