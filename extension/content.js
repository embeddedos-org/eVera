/**
 * eVera Chrome Extension — Content Script
 *
 * Detects text selection and shows floating action toolbar.
 */

(function () {
    "use strict";

    let toolbar = null;
    let resultTooltip = null;

    // --- Floating Toolbar ---
    function createToolbar() {
        if (toolbar) return toolbar;

        toolbar = document.createElement("div");
        toolbar.id = "vera-toolbar";
        toolbar.innerHTML = `
            <button data-action="summarize" title="Summarize">📝</button>
            <button data-action="translate" title="Translate">🌐</button>
            <button data-action="explain" title="Explain">💡</button>
            <button data-action="grammar" title="Fix Grammar">✏️</button>
            <button data-action="chat" title="Ask eVera">🤖</button>
        `;

        toolbar.addEventListener("click", (e) => {
            const btn = e.target.closest("button");
            if (!btn) return;

            const action = btn.dataset.action;
            const selectedText = window.getSelection().toString().trim();
            if (!selectedText) return;

            if (action === "chat") {
                chrome.runtime.sendMessage({
                    type: "send-chat",
                    text: selectedText,
                });
            } else {
                performAction(action, selectedText);
            }

            hideToolbar();
        });

        document.body.appendChild(toolbar);
        return toolbar;
    }

    function showToolbar(x, y) {
        const tb = createToolbar();
        tb.style.left = `${x}px`;
        tb.style.top = `${y}px`;
        tb.classList.add("visible");
    }

    function hideToolbar() {
        if (toolbar) {
            toolbar.classList.remove("visible");
        }
    }

    // --- Result Tooltip ---
    function showResult(text, x, y) {
        hideResult();

        resultTooltip = document.createElement("div");
        resultTooltip.id = "vera-result-tooltip";
        resultTooltip.innerHTML = `
            <div class="vera-result-header">
                <span>🤖 eVera</span>
                <button class="vera-result-close">✕</button>
            </div>
            <div class="vera-result-content">${escapeHtml(text)}</div>
            <button class="vera-result-copy">📋 Copy</button>
        `;

        resultTooltip.querySelector(".vera-result-close").addEventListener("click", hideResult);
        resultTooltip.querySelector(".vera-result-copy").addEventListener("click", () => {
            navigator.clipboard.writeText(text);
            const btn = resultTooltip.querySelector(".vera-result-copy");
            btn.textContent = "✅ Copied!";
            setTimeout(() => {
                btn.textContent = "📋 Copy";
            }, 2000);
        });

        document.body.appendChild(resultTooltip);

        // Position
        const rect = resultTooltip.getBoundingClientRect();
        const maxX = window.innerWidth - rect.width - 20;
        const maxY = window.innerHeight - rect.height - 20;
        resultTooltip.style.left = `${Math.min(x, maxX)}px`;
        resultTooltip.style.top = `${Math.min(y + 10, maxY)}px`;
    }

    function hideResult() {
        if (resultTooltip) {
            resultTooltip.remove();
            resultTooltip = null;
        }
    }

    // --- Actions ---
    async function performAction(action, text) {
        const { serverUrl } = await new Promise((resolve) => {
            chrome.runtime.sendMessage({ type: "get-status" }, resolve);
        });

        const url = (serverUrl || "http://localhost:8000") + `/extension/${action}`;

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });
            const result = await response.json();

            const sel = window.getSelection();
            if (sel.rangeCount > 0) {
                const range = sel.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                showResult(
                    result.result,
                    rect.left + window.scrollX,
                    rect.bottom + window.scrollY
                );
            }
        } catch (e) {
            console.error("[eVera] Action failed:", e);
            showResult("Error: Could not reach eVera backend.", 100, 100);
        }
    }

    // --- Selection Detection ---
    document.addEventListener("mouseup", (e) => {
        // Ignore clicks inside our own toolbar/tooltip
        if (e.target.closest("#vera-toolbar") || e.target.closest("#vera-result-tooltip")) {
            return;
        }

        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        if (selectedText.length > 3) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            showToolbar(
                rect.left + window.scrollX,
                rect.top + window.scrollY - 45
            );
        } else {
            hideToolbar();
        }
    });

    // Hide toolbar when clicking elsewhere
    document.addEventListener("mousedown", (e) => {
        if (!e.target.closest("#vera-toolbar") && !e.target.closest("#vera-result-tooltip")) {
            hideToolbar();
        }
    });

    // --- Message from background ---
    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === "vera-result") {
            const sel = window.getSelection();
            if (sel.rangeCount > 0) {
                const range = sel.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                showResult(
                    message.result,
                    rect.left + window.scrollX,
                    rect.bottom + window.scrollY
                );
            } else {
                showResult(message.result, 100, 100);
            }
        }
    });

    // --- Helpers ---
    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }
})();
