/**
 * Voca Desktop — Preload Script
 *
 * Secure bridge between Node.js and the renderer process.
 * Exposes a minimal API via contextBridge.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("vocaDesktop", {
    platform: process.platform,
    isElectron: true,

    // Window controls
    minimize: () => ipcRenderer.send("window:minimize"),
    maximize: () => ipcRenderer.send("window:maximize"),
    close: () => ipcRenderer.send("window:close"),

    // Notifications
    notify: (title, body) => ipcRenderer.send("notify", { title, body }),

    // Listen for notifications from main process
    onNotification: (callback) => {
        ipcRenderer.on("push-notification", (_event, data) => callback(data));
    },

    // App info
    getVersion: () => ipcRenderer.invoke("get-version"),
});
