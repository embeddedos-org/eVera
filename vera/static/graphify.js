/* === Vera Graphify — Canvas-Based Force-Directed Graph Renderer === */

var VeraGraphify = (function () {
    "use strict";

    var canvas = null;
    var ctx = null;
    var animId = null;
    var nodes = [];
    var edges = [];
    var currentMode = "memory"; // "memory" or "deps"

    // Layout state
    var layoutDone = false;
    var iteration = 0;
    var MAX_ITERATIONS = 120;

    // Pan/zoom
    var panX = 0;
    var panY = 0;
    var scale = 1;
    var dragging = false;
    var dragStartX = 0;
    var dragStartY = 0;
    var dragNode = null;

    // Hover
    var hoveredNode = null;
    var mouseX = 0;
    var mouseY = 0;

    // Particles for animated edges
    var particles = [];

    function init(canvasEl) {
        if (typeof canvasEl === "string") {
            canvas = document.getElementById(canvasEl);
        } else {
            canvas = canvasEl;
        }
        if (!canvas) return;
        ctx = canvas.getContext("2d");

        canvas.addEventListener("mousedown", onMouseDown);
        canvas.addEventListener("mousemove", onMouseMove);
        canvas.addEventListener("mouseup", onMouseUp);
        canvas.addEventListener("mouseleave", onMouseUp);
        canvas.addEventListener("wheel", onWheel, { passive: false });
        canvas.addEventListener("click", onClick);
    }

    function destroy() {
        if (animId) {
            cancelAnimationFrame(animId);
            animId = null;
        }
        nodes = [];
        edges = [];
        layoutDone = false;
        iteration = 0;
    }

    // --- Data Loading ---

    function loadMemoryGraph() {
        currentMode = "memory";
        destroy();

        fetch("/api/memory/graph")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                setGraphData(data.nodes || [], data.edges || []);
            })
            .catch(function (err) {
                console.error("Failed to load memory graph:", err);
            });
    }

    function loadDependencyGraph(path) {
        currentMode = "deps";
        destroy();

        var url = "/api/code/dependency-graph";
        if (path) url += "?path=" + encodeURIComponent(path);

        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                setGraphData(data.nodes || [], data.edges || []);
            })
            .catch(function (err) {
                console.error("Failed to load dependency graph:", err);
            });
    }

    function setGraphData(nodeData, edgeData) {
        nodes = [];
        edges = [];
        particles = [];
        layoutDone = false;
        iteration = 0;

        var rect = canvas.getBoundingClientRect();
        var cx = rect.width / 2;
        var cy = rect.height / 2;

        for (var i = 0; i < nodeData.length; i++) {
            var n = nodeData[i];
            nodes.push({
                id: n.id,
                label: n.label || n.id,
                type: n.type || "file",
                color: n.color || getTypeColor(n.type),
                radius: n.type === "hub" ? 30 : 15,
                path: n.path || "",
                count: n.count || 0,
                value: n.value || "",
                complexity: n.complexity || "low",
                x: cx + (Math.random() - 0.5) * 300,
                y: cy + (Math.random() - 0.5) * 300,
                vx: 0,
                vy: 0,
            });
        }

        for (var j = 0; j < edgeData.length; j++) {
            var e = edgeData[j];
            edges.push({
                source: e.source,
                target: e.target,
                type: e.type || "default",
            });
        }

        // Seed a few particles
        for (var k = 0; k < Math.min(edges.length, 10); k++) {
            particles.push({
                edgeIndex: k,
                t: Math.random(),
                speed: 0.003 + Math.random() * 0.003,
            });
        }

        startAnimation();
    }

    function getTypeColor(type) {
        var colors = {
            file: "#60a5fa",
            class: "#4ade80",
            function: "#a78bfa",
            hub: "#6c7bff",
            fact: "#4ade80",
        };
        return colors[type] || "#6c7bff";
    }

    // --- Force-Directed Layout ---

    function layoutStep() {
        if (layoutDone) return;

        var k = 80; // optimal distance
        var area = canvas.clientWidth * canvas.clientHeight;
        var kSq = k * k;
        var cooling = 1 - iteration / MAX_ITERATIONS;
        var temp = Math.max(0.5, cooling * 10);

        // Repulsion
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].vx = 0;
            nodes[i].vy = 0;
            for (var j = 0; j < nodes.length; j++) {
                if (i === j) continue;
                var dx = nodes[i].x - nodes[j].x;
                var dy = nodes[i].y - nodes[j].y;
                var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                var force = kSq / dist;
                nodes[i].vx += (dx / dist) * force * 0.05;
                nodes[i].vy += (dy / dist) * force * 0.05;
            }
        }

        // Attraction
        for (var e = 0; e < edges.length; e++) {
            var srcNode = findNode(edges[e].source);
            var tgtNode = findNode(edges[e].target);
            if (!srcNode || !tgtNode) continue;

            var edx = tgtNode.x - srcNode.x;
            var edy = tgtNode.y - srcNode.y;
            var eDist = Math.sqrt(edx * edx + edy * edy) || 1;
            var aForce = (eDist - k) * 0.03;

            srcNode.vx += (edx / eDist) * aForce;
            srcNode.vy += (edy / eDist) * aForce;
            tgtNode.vx -= (edx / eDist) * aForce;
            tgtNode.vy -= (edy / eDist) * aForce;
        }

        // Center gravity
        var cx = canvas.clientWidth / 2;
        var cy = canvas.clientHeight / 2;
        for (var n = 0; n < nodes.length; n++) {
            nodes[n].vx += (cx - nodes[n].x) * 0.001;
            nodes[n].vy += (cy - nodes[n].y) * 0.001;

            // Apply velocity with temp damping
            var speed = Math.sqrt(nodes[n].vx * nodes[n].vx + nodes[n].vy * nodes[n].vy);
            if (speed > temp) {
                nodes[n].vx = (nodes[n].vx / speed) * temp;
                nodes[n].vy = (nodes[n].vy / speed) * temp;
            }

            if (dragNode !== nodes[n]) {
                nodes[n].x += nodes[n].vx;
                nodes[n].y += nodes[n].vy;
            }
        }

        iteration++;
        if (iteration >= MAX_ITERATIONS) {
            layoutDone = true;
        }
    }

    function findNode(id) {
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].id === id) return nodes[i];
        }
        return null;
    }

    // --- Rendering ---

    function startAnimation() {
        if (animId) cancelAnimationFrame(animId);

        function frame() {
            if (!canvas) return;

            var rect = canvas.getBoundingClientRect();
            var dpr = window.devicePixelRatio || 1;
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            canvas.style.width = rect.width + "px";
            canvas.style.height = rect.height + "px";
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            layoutStep();
            draw(rect.width, rect.height);

            animId = requestAnimationFrame(frame);
        }

        frame();
    }

    function draw(w, h) {
        ctx.clearRect(0, 0, w, h);
        ctx.save();
        ctx.translate(panX, panY);
        ctx.scale(scale, scale);

        // Draw edges
        for (var e = 0; e < edges.length; e++) {
            var src = findNode(edges[e].source);
            var tgt = findNode(edges[e].target);
            if (!src || !tgt) continue;

            ctx.beginPath();
            var midX = (src.x + tgt.x) / 2;
            var midY = (src.y + tgt.y) / 2 - 20;
            ctx.moveTo(src.x, src.y);
            ctx.quadraticCurveTo(midX, midY, tgt.x, tgt.y);

            var isImport = edges[e].type === "imports";
            var isInherits = edges[e].type === "inherits";

            ctx.strokeStyle = isInherits ? "rgba(74, 222, 128, 0.4)"
                : isImport ? "rgba(108, 123, 255, 0.3)"
                : "rgba(255, 255, 255, 0.1)";
            ctx.lineWidth = isInherits ? 2.5 : 1.5;
            if (isImport) ctx.setLineDash([4, 4]);
            else ctx.setLineDash([]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Arrow
            drawArrow(src.x, src.y, tgt.x, tgt.y, tgt.radius || 15);
        }

        // Animated particles
        for (var p = 0; p < particles.length; p++) {
            var part = particles[p];
            if (part.edgeIndex >= edges.length) continue;

            var pEdge = edges[part.edgeIndex];
            var pSrc = findNode(pEdge.source);
            var pTgt = findNode(pEdge.target);
            if (!pSrc || !pTgt) continue;

            part.t += part.speed;
            if (part.t > 1) part.t = 0;

            var px = pSrc.x + (pTgt.x - pSrc.x) * part.t;
            var py = pSrc.y + (pTgt.y - pSrc.y) * part.t;

            ctx.beginPath();
            ctx.arc(px, py, 2.5, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(108, 123, 255, 0.7)";
            ctx.fill();
        }

        // Draw nodes
        for (var n = 0; n < nodes.length; n++) {
            var node = nodes[n];
            var isHovered = hoveredNode === node;
            var r = node.radius;

            // Glow
            if (isHovered || node.type === "hub") {
                var glowR = r + (isHovered ? 12 : 6);
                var glow = ctx.createRadialGradient(node.x, node.y, r * 0.5, node.x, node.y, glowR);
                glow.addColorStop(0, hexToRgba(node.color, 0.25));
                glow.addColorStop(1, "transparent");
                ctx.beginPath();
                ctx.arc(node.x, node.y, glowR, 0, Math.PI * 2);
                ctx.fillStyle = glow;
                ctx.fill();
            }

            // Circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
            ctx.fillStyle = hexToRgba(node.color, 0.2);
            ctx.fill();
            ctx.strokeStyle = hexToRgba(node.color, isHovered ? 0.9 : 0.5);
            ctx.lineWidth = isHovered ? 2 : 1;
            ctx.stroke();

            // Label
            ctx.font = (node.type === "hub" ? "bold 12px" : "11px") + " -apple-system, BlinkMacSystemFont, sans-serif";
            ctx.fillStyle = isHovered ? "#ffffff" : hexToRgba(node.color, 0.9);
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";

            var label = node.label;
            if (label.length > 16) label = label.substring(0, 14) + "…";
            ctx.fillText(label, node.x, node.y + r + 14);

            // Count badge for hub nodes
            if (node.type === "hub" && node.count > 0) {
                ctx.font = "bold 11px monospace";
                ctx.fillStyle = "#ffffff";
                ctx.fillText(String(node.count), node.x, node.y);
            }

            // Type icon
            if (node.type !== "hub") {
                var icons = { file: "📄", class: "🏗️", function: "⚡", fact: "💡" };
                ctx.font = "12px sans-serif";
                ctx.fillText(icons[node.type] || "•", node.x, node.y);
            }
        }

        // Tooltip
        if (hoveredNode) {
            drawTooltip(hoveredNode, w, h);
        }

        ctx.restore();
    }

    function drawArrow(x1, y1, x2, y2, targetR) {
        var angle = Math.atan2(y2 - y1, x2 - x1);
        var tipX = x2 - Math.cos(angle) * targetR;
        var tipY = y2 - Math.sin(angle) * targetR;
        var size = 6;

        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - size * Math.cos(angle - 0.4), tipY - size * Math.sin(angle - 0.4));
        ctx.lineTo(tipX - size * Math.cos(angle + 0.4), tipY - size * Math.sin(angle + 0.4));
        ctx.closePath();
        ctx.fillStyle = "rgba(108, 123, 255, 0.5)";
        ctx.fill();
    }

    function drawTooltip(node, w, h) {
        var lines = [node.label];
        if (node.type) lines.push("Type: " + node.type);
        if (node.path) lines.push("Path: " + truncate(node.path, 30));
        if (node.complexity && node.complexity !== "low") lines.push("Complexity: " + node.complexity);
        if (node.value) lines.push("Value: " + truncate(node.value, 30));
        if (node.count > 0) lines.push("Count: " + node.count);

        var ttW = 200;
        var ttH = 14 + lines.length * 16;
        var ttX = Math.min(node.x + node.radius + 10, (w - panX) / scale - ttW - 10);
        var ttY = Math.max(node.y - ttH / 2, 10);

        ctx.fillStyle = "rgba(10, 14, 26, 0.95)";
        ctx.strokeStyle = "rgba(108, 123, 255, 0.3)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        roundRect(ctx, ttX, ttY, ttW, ttH, 8);
        ctx.fill();
        ctx.stroke();

        ctx.font = "10px monospace";
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        for (var i = 0; i < lines.length; i++) {
            ctx.fillStyle = i === 0 ? "#6c7bff" : "#8b90b0";
            ctx.fillText(lines[i], ttX + 10, ttY + 8 + i * 16);
        }
    }

    // --- Interaction ---

    function onMouseDown(e) {
        var pos = screenToWorld(e);
        var hit = hitTest(pos.x, pos.y);

        if (hit) {
            dragNode = hit;
        } else {
            dragging = true;
            dragStartX = e.clientX - panX;
            dragStartY = e.clientY - panY;
        }
        canvas.style.cursor = "grabbing";
    }

    function onMouseMove(e) {
        var rect = canvas.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;

        if (dragNode) {
            var pos = screenToWorld(e);
            dragNode.x = pos.x;
            dragNode.y = pos.y;
        } else if (dragging) {
            panX = e.clientX - dragStartX;
            panY = e.clientY - dragStartY;
        } else {
            var wPos = screenToWorld(e);
            hoveredNode = hitTest(wPos.x, wPos.y);
            canvas.style.cursor = hoveredNode ? "pointer" : "grab";
        }
    }

    function onMouseUp() {
        dragging = false;
        dragNode = null;
        canvas.style.cursor = "grab";
    }

    function onWheel(e) {
        e.preventDefault();
        var factor = e.deltaY < 0 ? 1.1 : 0.9;
        scale = Math.max(0.2, Math.min(5.0, scale * factor));
    }

    function onClick(e) {
        if (currentMode === "deps") {
            var pos = screenToWorld(e);
            var hit = hitTest(pos.x, pos.y);
            if (hit && hit.path && typeof VeraCodeViewer !== "undefined") {
                VeraCodeViewer.openFile(hit.path);
                var modal = document.getElementById("graphModal");
                if (modal) modal.classList.remove("open");
                destroy();
            }
        }
    }

    function screenToWorld(e) {
        var rect = canvas.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left - panX) / scale,
            y: (e.clientY - rect.top - panY) / scale,
        };
    }

    function hitTest(wx, wy) {
        for (var i = nodes.length - 1; i >= 0; i--) {
            var n = nodes[i];
            var dx = wx - n.x;
            var dy = wy - n.y;
            if (dx * dx + dy * dy < (n.radius + 5) * (n.radius + 5)) {
                return n;
            }
        }
        return null;
    }

    // --- Helpers ---

    function hexToRgba(hex, alpha) {
        if (hex.startsWith("rgba") || hex.startsWith("rgb")) return hex;
        var r = parseInt(hex.slice(1, 3), 16) || 0;
        var g = parseInt(hex.slice(3, 5), 16) || 0;
        var b = parseInt(hex.slice(5, 7), 16) || 0;
        return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
    }

    function truncate(str, max) {
        return str.length > max ? str.substring(0, max - 1) + "…" : str;
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

    return {
        init: init,
        destroy: destroy,
        loadMemoryGraph: loadMemoryGraph,
        loadDependencyGraph: loadDependencyGraph,
    };
})();
