/**
 * Voca Desktop — Electron Main Process
 *
 * Features:
 * - Frameless window with custom title bar
 * - System tray with status indicator
 * - Global keyboard shortcut (Ctrl+Shift+V)
 * - Desktop notifications
 * - Single-instance lock
 * - Auto-start on boot (optional)
 */

const {
    app,
    BrowserWindow,
    Tray,
    Menu,
    globalShortcut,
    Notification,
    nativeImage,
    shell,
} = require("electron");
const path = require("path");

let Store;
try {
    Store = require("electron-store");
} catch {
    Store = null;
}

const VOCA_URL = process.env.VOCA_URL || "http://localhost:8000";
const IS_DEV = !app.isPackaged;

let mainWindow = null;
let tray = null;
let store = null;

// --- Single Instance Lock ---
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
    app.quit();
} else {
    app.on("second-instance", () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.show();
            mainWindow.focus();
        }
    });
}

// --- Store ---
function initStore() {
    if (Store) {
        store = new Store({
            defaults: {
                autoStart: false,
                windowBounds: { width: 1200, height: 800 },
                alwaysOnTop: false,
            },
        });
    }
}

function getSetting(key, fallback) {
    if (store) return store.get(key, fallback);
    return fallback;
}

function setSetting(key, value) {
    if (store) store.set(key, value);
}

// --- Window ---

function createWindow() {
    const bounds = getSetting("windowBounds", { width: 1200, height: 800 });

    mainWindow = new BrowserWindow({
        width: bounds.width,
        height: bounds.height,
        minWidth: 800,
        minHeight: 600,
        title: "Voca",
        icon: getIcon("icon.png"),
        backgroundColor: "#070b14",
        show: false,
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    mainWindow.loadURL(VOCA_URL);

    mainWindow.once("ready-to-show", () => {
        mainWindow.show();
    });

    mainWindow.on("close", (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    mainWindow.on("resize", () => {
        const { width, height } = mainWindow.getBounds();
        setSetting("windowBounds", { width, height });
    });

    // Open external links in browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: "deny" };
    });

    return mainWindow;
}

// --- System Tray ---

function createTray() {
    const icon = getIcon("tray-icon.png") || getIcon("icon.png");
    tray = new Tray(icon);
    tray.setToolTip("Voca — AI Buddy");

    const contextMenu = Menu.buildFromTemplate([
        {
            label: "Show Voca",
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            },
        },
        {
            label: "Hide",
            click: () => {
                if (mainWindow) mainWindow.hide();
            },
        },
        { type: "separator" },
        {
            label: "Always on Top",
            type: "checkbox",
            checked: getSetting("alwaysOnTop", false),
            click: (item) => {
                setSetting("alwaysOnTop", item.checked);
                if (mainWindow) mainWindow.setAlwaysOnTop(item.checked);
            },
        },
        {
            label: "Start on Boot",
            type: "checkbox",
            checked: getSetting("autoStart", false),
            click: (item) => {
                setSetting("autoStart", item.checked);
                app.setLoginItemSettings({
                    openAtLogin: item.checked,
                    path: app.getPath("exe"),
                });
            },
        },
        { type: "separator" },
        {
            label: "Quit Voca",
            click: () => {
                app.isQuitting = true;
                app.quit();
            },
        },
    ]);

    tray.setContextMenu(contextMenu);

    tray.on("click", () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });
}

// --- Global Shortcut ---

function registerGlobalShortcut() {
    const ret = globalShortcut.register("CommandOrControl+Shift+V", () => {
        if (mainWindow) {
            if (mainWindow.isVisible() && mainWindow.isFocused()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });

    if (!ret) {
        console.warn("Global shortcut Ctrl+Shift+V registration failed");
    }
}

// --- Notifications ---

function showNotification(title, body) {
    if (Notification.isSupported()) {
        const notification = new Notification({
            title: title || "Voca",
            body: body || "",
            icon: getIcon("icon.png"),
        });
        notification.show();

        notification.on("click", () => {
            if (mainWindow) {
                mainWindow.show();
                mainWindow.focus();
            }
        });
    }
}

// --- Helpers ---

function getIcon(filename) {
    const iconPath = path.join(__dirname, filename);
    try {
        return nativeImage.createFromPath(iconPath);
    } catch {
        return null;
    }
}

// --- App Lifecycle ---

app.on("ready", () => {
    initStore();
    createWindow();
    createTray();
    registerGlobalShortcut();

    // Apply saved settings
    if (mainWindow && getSetting("alwaysOnTop", false)) {
        mainWindow.setAlwaysOnTop(true);
    }

    // Auto-start setting
    if (getSetting("autoStart", false)) {
        app.setLoginItemSettings({
            openAtLogin: true,
            path: app.getPath("exe"),
        });
    }
});

app.on("window-all-closed", () => {
    // Don't quit on macOS
    if (process.platform !== "darwin") {
        // But we minimize to tray instead of quitting
    }
});

app.on("activate", () => {
    if (mainWindow === null) {
        createWindow();
    } else {
        mainWindow.show();
    }
});

app.on("will-quit", () => {
    globalShortcut.unregisterAll();
});

app.on("before-quit", () => {
    app.isQuitting = true;
});

// Export for potential IPC usage
module.exports = { showNotification };
