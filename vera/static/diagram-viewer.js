/* === Vera Diagram Viewer — Mermaid Rendering with Pan/Zoom/Export === */

var VeraDiagramViewer = (function () {
    "use strict";

    var diagramCounter = 0;
    var fullscreenOverlay = null;

    function render(mermaidText, targetEl) {
        if (!mermaidText || !targetEl) return;
        if (typeof mermaid === "undefined") {
            targetEl.innerHTML = '<pre style="color:#f43f5e;">Mermaid.js not loaded</pre>';
            return;
        }

        diagramCounter++;
        var id = "vera-diagram-" + diagramCounter;

        try {
            mermaid.render(id, mermaidText).then(function (result) {
                targetEl.innerHTML = "";

                var wrapper = document.createElement("div");
                wrapper.className = "diagram-pan-zoom";
                wrapper.innerHTML = result.svg;
                targetEl.appendChild(wrapper);

                // Add toolbar
                var toolbar = createToolbar(wrapper, mermaidText);
                targetEl.appendChild(toolbar);

                // Enable pan/zoom
                enablePanZoom(wrapper);
            }).catch(function (err) {
                targetEl.innerHTML = '<pre style="color:#f43f5e;">Diagram error: ' + escapeHtml(err.message || String(err)) + '</pre>';
            });
        } catch (err) {
            targetEl.innerHTML = '<pre style="color:#f43f5e;">Diagram error: ' + escapeHtml(String(err)) + '</pre>';
        }
    }

    function createToolbar(wrapper, mermaidText) {
        var toolbar = document.createElement("div");
        toolbar.className = "diagram-toolbar";

        var btnZoomIn = makeBtn("🔍+", "Zoom in", function () {
            zoom(wrapper, 1.2);
        });
        var btnZoomOut = makeBtn("🔍−", "Zoom out", function () {
            zoom(wrapper, 0.8);
        });
        var btnFit = makeBtn("⊡", "Fit to screen", function () {
            resetTransform(wrapper);
        });
        var btnSvg = makeBtn("SVG", "Download SVG", function () {
            exportSvg(wrapper);
        });
        var btnPng = makeBtn("PNG", "Download PNG", function () {
            exportPng(wrapper);
        });
        var btnFullscreen = makeBtn("⛶", "Full screen", function () {
            openFullscreen(wrapper, mermaidText);
        });

        toolbar.appendChild(btnZoomIn);
        toolbar.appendChild(btnZoomOut);
        toolbar.appendChild(btnFit);
        toolbar.appendChild(btnSvg);
        toolbar.appendChild(btnPng);
        toolbar.appendChild(btnFullscreen);

        return toolbar;
    }

    function makeBtn(label, title, onClick) {
        var btn = document.createElement("button");
        btn.className = "diagram-tool-btn";
        btn.textContent = label;
        btn.title = title;
        btn.addEventListener("click", onClick);
        return btn;
    }

    // --- Pan/Zoom ---

    function enablePanZoom(wrapper) {
        var state = { scale: 1, panX: 0, panY: 0, dragging: false, startX: 0, startY: 0 };
        wrapper._pzState = state;

        wrapper.style.cursor = "grab";
        wrapper.style.transformOrigin = "0 0";

        wrapper.addEventListener("mousedown", function (e) {
            state.dragging = true;
            state.startX = e.clientX - state.panX;
            state.startY = e.clientY - state.panY;
            wrapper.style.cursor = "grabbing";
            e.preventDefault();
        });

        wrapper.addEventListener("mousemove", function (e) {
            if (!state.dragging) return;
            state.panX = e.clientX - state.startX;
            state.panY = e.clientY - state.startY;
            applyTransform(wrapper, state);
        });

        wrapper.addEventListener("mouseup", function () {
            state.dragging = false;
            wrapper.style.cursor = "grab";
        });

        wrapper.addEventListener("mouseleave", function () {
            state.dragging = false;
            wrapper.style.cursor = "grab";
        });

        wrapper.addEventListener("wheel", function (e) {
            e.preventDefault();
            var factor = e.deltaY < 0 ? 1.1 : 0.9;
            state.scale = Math.max(0.2, Math.min(5, state.scale * factor));
            applyTransform(wrapper, state);
        }, { passive: false });
    }

    function applyTransform(wrapper, state) {
        wrapper.style.transform = "translate(" + state.panX + "px, " + state.panY + "px) scale(" + state.scale + ")";
    }

    function zoom(wrapper, factor) {
        var state = wrapper._pzState;
        if (!state) return;
        state.scale = Math.max(0.2, Math.min(5, state.scale * factor));
        applyTransform(wrapper, state);
    }

    function resetTransform(wrapper) {
        var state = wrapper._pzState;
        if (!state) return;
        state.scale = 1;
        state.panX = 0;
        state.panY = 0;
        applyTransform(wrapper, state);
    }

    // --- Export ---

    function exportSvg(wrapper) {
        var svg = wrapper.querySelector("svg");
        if (!svg) return;

        var clone = svg.cloneNode(true);
        var svgString = new XMLSerializer().serializeToString(clone);
        var blob = new Blob([svgString], { type: "image/svg+xml" });
        downloadBlob(blob, "diagram.svg");
    }

    function exportPng(wrapper) {
        var svg = wrapper.querySelector("svg");
        if (!svg) return;

        var clone = svg.cloneNode(true);
        var svgString = new XMLSerializer().serializeToString(clone);
        var svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
        var url = URL.createObjectURL(svgBlob);

        var img = new Image();
        img.onload = function () {
            var canvas = document.createElement("canvas");
            canvas.width = img.width * 2;
            canvas.height = img.height * 2;
            var ctx = canvas.getContext("2d");
            ctx.scale(2, 2);
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(url);

            canvas.toBlob(function (blob) {
                if (blob) downloadBlob(blob, "diagram.png");
            }, "image/png");
        };
        img.src = url;
    }

    function downloadBlob(blob, filename) {
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    }

    // --- Fullscreen Modal ---

    function openFullscreen(wrapper, mermaidText) {
        closeFullscreen();

        fullscreenOverlay = document.createElement("div");
        fullscreenOverlay.className = "diagram-fullscreen";

        var closeBtn = document.createElement("button");
        closeBtn.className = "diagram-fullscreen-close";
        closeBtn.textContent = "✕";
        closeBtn.addEventListener("click", closeFullscreen);

        var container = document.createElement("div");
        container.className = "diagram-fullscreen-container";

        fullscreenOverlay.appendChild(closeBtn);
        fullscreenOverlay.appendChild(container);
        document.body.appendChild(fullscreenOverlay);

        // Render diagram in fullscreen
        render(mermaidText, container);

        // Close on Escape
        document.addEventListener("keydown", onEscKey);
    }

    function closeFullscreen() {
        if (fullscreenOverlay) {
            document.body.removeChild(fullscreenOverlay);
            fullscreenOverlay = null;
        }
        document.removeEventListener("keydown", onEscKey);
    }

    function onEscKey(e) {
        if (e.key === "Escape") closeFullscreen();
    }

    // --- Chat Integration ---

    function renderMermaidInChat(messageEl) {
        if (!messageEl) return;

        var bubbles = messageEl.querySelectorAll(".message-bubble");
        bubbles.forEach(function (bubble) {
            var text = bubble.textContent || "";
            var mermaidRegex = /```mermaid\n([\s\S]*?)```/g;
            var match;

            while ((match = mermaidRegex.exec(text)) !== null) {
                var mermaidText = match[1].trim();
                var block = document.createElement("div");
                block.className = "diagram-chat-block";

                var diagramContainer = document.createElement("div");
                diagramContainer.className = "diagram-container";
                block.appendChild(diagramContainer);

                var openBtn = document.createElement("button");
                openBtn.className = "diagram-open-btn";
                openBtn.textContent = "🔍 Open in Viewer";
                openBtn.addEventListener("click", (function (mt) {
                    return function () { openFullscreen(null, mt); };
                })(mermaidText));
                block.appendChild(openBtn);

                // Replace the text with the rendered diagram
                var beforeText = text.substring(0, match.index);
                var afterText = text.substring(match.index + match[0].length);

                bubble.textContent = "";
                if (beforeText.trim()) {
                    var pre = document.createElement("span");
                    pre.textContent = beforeText;
                    bubble.appendChild(pre);
                }
                bubble.appendChild(block);
                if (afterText.trim()) {
                    var post = document.createElement("span");
                    post.textContent = afterText;
                    bubble.appendChild(post);
                }

                render(mermaidText, diagramContainer);

                // Only handle first mermaid block per bubble to keep simple
                break;
            }
        });
    }

    // --- Helpers ---

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str || "";
        return div.innerHTML;
    }

    // Initialize mermaid with dark theme
    if (typeof mermaid !== "undefined") {
        mermaid.initialize({
            startOnLoad: false,
            theme: "dark",
            themeVariables: {
                darkMode: true,
                background: "#0a0e1a",
                primaryColor: "#1e2444",
                primaryTextColor: "#e8eaf6",
                primaryBorderColor: "#6c7bff",
                lineColor: "#6c7bff",
                secondaryColor: "#1a1f3a",
                tertiaryColor: "#141830",
            },
        });
    }

    return {
        render: render,
        renderMermaidInChat: renderMermaidInChat,
        openFullscreen: openFullscreen,
        closeFullscreen: closeFullscreen,
        exportSvg: exportSvg,
        exportPng: exportPng,
    };
})();
