/**
 * eVera Chrome Extension — Options Page
 */

(function () {
    "use strict";

    const serverUrlInput = document.getElementById("serverUrl");
    const defaultModelInput = document.getElementById("defaultModel");
    const showOverlayInput = document.getElementById("showOverlay");
    const saveBtn = document.getElementById("saveBtn");
    const saveStatus = document.getElementById("saveStatus");

    // Load saved settings
    chrome.storage.sync.get(
        ["serverUrl", "defaultModel", "showOverlay"],
        (result) => {
            serverUrlInput.value = result.serverUrl || "http://localhost:8000";
            defaultModelInput.value = result.defaultModel || "";
            showOverlayInput.checked = result.showOverlay !== false;
        }
    );

    // Save settings
    saveBtn.addEventListener("click", () => {
        const newUrl = serverUrlInput.value.trim().replace(/\/$/, "");
        const settings = {
            serverUrl: newUrl || "http://localhost:8000",
            defaultModel: defaultModelInput.value.trim(),
            showOverlay: showOverlayInput.checked,
        };

        chrome.storage.sync.set(settings, () => {
            // Notify background to reconnect with new URL
            chrome.runtime.sendMessage({
                type: "update-server-url",
                url: settings.serverUrl,
            });

            saveStatus.style.display = "block";
            setTimeout(() => {
                saveStatus.style.display = "none";
            }, 3000);
        });
    });
})();
