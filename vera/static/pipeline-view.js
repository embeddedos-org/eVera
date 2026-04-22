/* === Vera Pipeline View — Real-time DAG Visualization === */

var VeraPipelineView = (function () {
    "use strict";

    let canvas = null;
    let ctx = null;
    let animId = null;
    let container = null;

    // Node definitions — mirrors graph.py topology
    const NODE_DEFS = [
        { id: "enrich_memory",  label: "Enrich Memory",  icon: "🧠", x: 0.5, y: 0.06 },
        { id: "classify",       label: "Classify",        icon: "🏷️", x: 0.5, y: 0.19 },
        { id: "safety_check",   label: "Safety Check",    icon: "🛡️", x: 0.5, y: 0.32 },
        { id: "tier0_handler",  label: "Tier 0 Handler",  icon: "⚡", x: 0.2, y: 0.48 },
        { id: "agent",          label: "Agent",           icon: "🤖", x: 0.5, y: 0.48 },
        { id: "confirmation",   label: "Confirmation",    icon: "❓", x: 0.8, y: 0.48 },
        { id: "store_memory",   label: "Store Memory",    icon: "💾", x: 0.5, y: 0.64 },
        { id: "synthesize",     label: "Synthesize",      icon: "✨", x: 0.5, y: 0.80 },
    ];

    // Edges — directed
    const EDGES = [
        { from: "enrich_memory",  to: "classify" },
        { from: "classify",       to: "safety_check" },
        { from: "safety_check",   to: "tier0_handler",  conditional: true },
        { from: "safety_check",   to: "agent",          conditional: true },
        { from: "safety_check",   to: "confirmation",   conditional: true },
        { from: "safety_check",   to: "store_memory",   conditional: true },
        { from: "tier0_handler",  to: "store_memory" },
        { from: "agent",          to: "store_memory" },
        { from: "confirmation",   to: "store_memory" },
        { from: "store_memory",   to: "synthesize" },
    ];

    // Runtime state per node
    let nodeStates = {};
    let pipelineActive = false;
    let pipelineStartTime = 0;
    let hoveredNode = null;
    let tooltipData = null;

    function resetStates() {
        NODE_DEFS.forEach(function (n) {
            nodeStates[n.id] = { status: "idle", startTime: 0, data: null, elapsed: 0 };
        });
    }
    resetStates();

    function init(canvasEl) {
        if (typeof canvasEl === "string") {
            canvas = document.getElementById(canvasEl);
        } else {
            canvas = canvasEl;
        }
        if (!canvas) return;
        ctx = canvas.getContext("2d");

        canvas.addEventListener("mousemove", onMouseMove);
        canvas.addEventListener("mouseleave", function () {
            hoveredNode = null;
            tooltipData = null;
        });
    }

    function handlePipelineEvent(event) {
        if (event.type !== "pipeline") return;

        var node = event.node;
        var status = event.status;

        if (node === "pipeline") {
            if (status === "start") {
                pipelineActive = true;
                pipelineStartTime = Date.now();
                resetStates();
            } else if (status === "end") {
                pipelineActive = false;
            }
            return;
        }

        if (!nodeStates[node]) return;

        if (status === "working") {
            nodeStates[node].status = "working";
            nodeStates[node].startTime = Date.now();
        } else if (status === "done") {
            nodeStates[node].status = "done";
            nodeStates[node].elapsed = Date.now() - (nodeStates[node].startTime || Date.now());
            var data = Object.assign({}, event);
            delete data.type;
            delete data.node;
            delete data.status;
            nodeStates[node].data = data;
        }
    }

    function getNodePixelPos(nodeDef, w, h) {
        var padX = 80;
        var padY = 50;
        return {
            x: padX + nodeDef.x * (w - padX * 2),
            y: padY + nodeDef.y * (h - padY * 2),
        };
    }

    function onMouseMove(e) {
        if (!canvas) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var w = rect.width;
        var h = rect.height;

        hoveredNode = null;
        tooltipData = null;

        for (var i = 0; i < NODE_DEFS.length; i++) {
            var nd = NODE_DEFS[i];
            var pos = getNodePixelPos(nd, w, h);
            var dx = mx - pos.x;
            var dy = my - pos.y;
            if (dx * dx + dy * dy < 35 * 35) {
                hoveredNode = nd.id;
                tooltipData = nodeStates[nd.id];
                break;
            }
        }
    }

    function render() {
        container = document.getElementById("agentViewContainer");
        if (!container) return;

        if (!canvas || !container.contains(canvas)) {
            container.innerHTML = "";
            canvas = document.createElement("canvas");
            canvas.className = "pipeline-canvas";
            container.appendChild(canvas);
            ctx = canvas.getContext("2d");
            canvas.addEventListener("mousemove", onMouseMove);
            canvas.addEventListener("mouseleave", function () {
                hoveredNode = null;
                tooltipData = null;
            });
        }

        if (animId) cancelAnimationFrame(animId);

        function drawFrame() {
            var rect = container.getBoundingClientRect();
            var dpr = window.devicePixelRatio || 1;
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = rect.width + "px";
            canvas.style.height = rect.height + "px";
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            var w = rect.width;
            var h = rect.height;

            ctx.clearRect(0, 0, w, h);

            // Build position map
            var positions = {};
            NODE_DEFS.forEach(function (nd) {
                positions[nd.id] = getNodePixelPos(nd, w, h);
            });

            // Draw edges
            EDGES.forEach(function (edge) {
                var fromPos = positions[edge.from];
                var toPos = positions[edge.to];
                if (!fromPos || !toPos) return;

                var fromState = nodeStates[edge.from] || {};
                var toState = nodeStates[edge.to] || {};
                var isActive = fromState.status === "done" && toState.status === "working";
                var isDone = fromState.status === "done" && toState.status === "done";

                ctx.beginPath();
                // Bezier curve
                var midY = (fromPos.y + toPos.y) / 2;
                ctx.moveTo(fromPos.x, fromPos.y + 20);
                ctx.bezierCurveTo(fromPos.x, midY, toPos.x, midY, toPos.x, toPos.y - 20);

                ctx.strokeStyle = isDone ? "rgba(74, 222, 128, 0.35)"
                    : isActive ? "rgba(108, 123, 255, 0.5)"
                    : edge.conditional ? "rgba(255, 255, 255, 0.06)"
                    : "rgba(255, 255, 255, 0.1)";
                ctx.lineWidth = isActive ? 2.5 : 1.5;
                if (edge.conditional) ctx.setLineDash([6, 4]);
                else ctx.setLineDash([]);
                ctx.stroke();
                ctx.setLineDash([]);

                // Arrow head
                var arrowSize = 6;
                var angle = Math.atan2(toPos.y - 20 - midY, toPos.x - toPos.x) || -Math.PI / 2;
                ctx.beginPath();
                ctx.moveTo(toPos.x, toPos.y - 20);
                ctx.lineTo(toPos.x - arrowSize * Math.cos(angle - 0.4), toPos.y - 20 - arrowSize * Math.sin(angle - 0.4));
                ctx.lineTo(toPos.x - arrowSize * Math.cos(angle + 0.4), toPos.y - 20 - arrowSize * Math.sin(angle + 0.4));
                ctx.closePath();
                ctx.fillStyle = isDone ? "rgba(74, 222, 128, 0.5)" : isActive ? "rgba(108, 123, 255, 0.7)" : "rgba(255, 255, 255, 0.15)";
                ctx.fill();

                // Animated particle along edge when active
                if (isActive) {
                    var t = (Date.now() % 1500) / 1500;
                    var px = fromPos.x + (toPos.x - fromPos.x) * t;
                    var py = (fromPos.y + 20) + (toPos.y - 20 - fromPos.y - 20) * t;
                    ctx.beginPath();
                    ctx.arc(px, py, 3, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(108, 123, 255, 0.8)";
                    ctx.fill();
                }
            });

            // Draw nodes
            NODE_DEFS.forEach(function (nd) {
                var pos = positions[nd.id];
                var state = nodeStates[nd.id] || {};
                var isWorking = state.status === "working";
                var isDone = state.status === "done";
                var isHovered = hoveredNode === nd.id;
                var nodeW = 120;
                var nodeH = 40;

                // Glow for working nodes
                if (isWorking) {
                    var glowR = 30 + Math.sin(Date.now() * 0.004) * 8;
                    var grad = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowR);
                    grad.addColorStop(0, "rgba(108, 123, 255, 0.25)");
                    grad.addColorStop(1, "transparent");
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, glowR, 0, Math.PI * 2);
                    ctx.fillStyle = grad;
                    ctx.fill();
                }

                // Rounded rectangle
                var rx = pos.x - nodeW / 2;
                var ry = pos.y - nodeH / 2;
                var r = 10;
                ctx.beginPath();
                ctx.moveTo(rx + r, ry);
                ctx.lineTo(rx + nodeW - r, ry);
                ctx.quadraticCurveTo(rx + nodeW, ry, rx + nodeW, ry + r);
                ctx.lineTo(rx + nodeW, ry + nodeH - r);
                ctx.quadraticCurveTo(rx + nodeW, ry + nodeH, rx + nodeW - r, ry + nodeH);
                ctx.lineTo(rx + r, ry + nodeH);
                ctx.quadraticCurveTo(rx, ry + nodeH, rx, ry + nodeH - r);
                ctx.lineTo(rx, ry + r);
                ctx.quadraticCurveTo(rx, ry, rx + r, ry);
                ctx.closePath();

                // Fill
                ctx.fillStyle = isWorking ? "rgba(20, 25, 50, 0.9)"
                    : isDone ? "rgba(15, 30, 20, 0.85)"
                    : "rgba(15, 18, 35, 0.8)";
                ctx.fill();

                // Border
                ctx.strokeStyle = isWorking ? "rgba(108, 123, 255, 0.7)"
                    : isDone ? "rgba(74, 222, 128, 0.5)"
                    : isHovered ? "rgba(255, 255, 255, 0.2)"
                    : "rgba(255, 255, 255, 0.08)";
                ctx.lineWidth = isWorking ? 2 : 1;
                ctx.stroke();

                // Icon
                ctx.font = "14px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(nd.icon, pos.x - 38, pos.y);

                // Label
                ctx.font = "11px -apple-system, BlinkMacSystemFont, sans-serif";
                ctx.fillStyle = isWorking ? "#6c7bff"
                    : isDone ? "#4ade80"
                    : "rgba(139, 144, 176, 0.8)";
                ctx.textAlign = "center";
                ctx.fillText(nd.label, pos.x + 8, pos.y);

                // Elapsed time for working nodes
                if (isWorking && state.startTime) {
                    var el = ((Date.now() - state.startTime) / 1000).toFixed(1);
                    ctx.font = "9px monospace";
                    ctx.fillStyle = "rgba(108, 123, 255, 0.7)";
                    ctx.fillText(el + "s", pos.x + 50, pos.y);
                }

                // Elapsed time badge for done nodes
                if (isDone && state.elapsed) {
                    var elS = (state.elapsed / 1000).toFixed(1);
                    ctx.font = "9px monospace";
                    ctx.fillStyle = "rgba(74, 222, 128, 0.6)";
                    ctx.fillText(elS + "s", pos.x + 50, pos.y);
                }
            });

            // Tooltip
            if (hoveredNode && tooltipData && tooltipData.data) {
                var hnd = NODE_DEFS.find(function (n) { return n.id === hoveredNode; });
                if (hnd) {
                    var tPos = getNodePixelPos(hnd, w, h);
                    var entries = Object.entries(tooltipData.data);
                    if (entries.length > 0) {
                        var ttW = 180;
                        var ttH = 20 + entries.length * 16;
                        var ttX = Math.min(tPos.x + 70, w - ttW - 10);
                        var ttY = Math.max(tPos.y - ttH / 2, 10);

                        // Background
                        ctx.fillStyle = "rgba(10, 14, 26, 0.95)";
                        ctx.strokeStyle = "rgba(108, 123, 255, 0.3)";
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        roundRect(ctx, ttX, ttY, ttW, ttH, 8);
                        ctx.fill();
                        ctx.stroke();

                        // Content
                        ctx.font = "10px monospace";
                        ctx.textAlign = "left";
                        entries.forEach(function (pair, idx) {
                            var k = pair[0];
                            var v = String(pair[1]).substring(0, 20);
                            ctx.fillStyle = "#6c7bff";
                            ctx.fillText(k + ":", ttX + 10, ttY + 16 + idx * 16);
                            ctx.fillStyle = "#e8eaf6";
                            ctx.fillText(v, ttX + 10 + ctx.measureText(k + ": ").width, ttY + 16 + idx * 16);
                        });
                    }
                }
            }

            // Pipeline elapsed counter
            if (pipelineActive && pipelineStartTime) {
                var totalEl = ((Date.now() - pipelineStartTime) / 1000).toFixed(1);
                ctx.font = "11px monospace";
                ctx.fillStyle = "rgba(108, 123, 255, 0.8)";
                ctx.textAlign = "right";
                ctx.fillText("Pipeline: " + totalEl + "s", w - 12, h - 12);
            }

            animId = requestAnimationFrame(drawFrame);
        }

        drawFrame();
    }

    function roundRect(ctx, x, y, w, h, r) {
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
    }

    function destroy() {
        if (animId) {
            cancelAnimationFrame(animId);
            animId = null;
        }
    }

    return {
        init: init,
        handlePipelineEvent: handlePipelineEvent,
        render: render,
        destroy: destroy,
    };
})();
