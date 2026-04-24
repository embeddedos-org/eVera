/**
 * Vera Desktop — Electron Main Process
 *
 * Features:
 * - Auto-starts bundled Python backend
 * - Frameless window with custom title bar
 * - System tray with status indicator
 * - Global keyboard shortcut (Ctrl+Shift+V)
 * - Desktop notifications
 * - Single-instance lock
 * - Auto-start on boot (optional)
 * - Splash screen while backend loads
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
    ipcMain,
    dialog,
} = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

let Store;
try {
    Store = require("electron-store");
} catch {
    Store = null;
}

const BACKEND_PORT = parseInt(process.env.VERA_PORT || "8000", 10);
const VERA_URL = process.env.VERA_URL || `http://localhost:${BACKEND_PORT}`;
const IS_DEV = !app.isPackaged;
const HEALTH_CHECK_INTERVAL = 1000;
const HEALTH_CHECK_TIMEOUT = 120000;

let mainWindow = null;
let splashWindow = null;
let tray = null;
let store = null;
let backendProcess = null;
let backendRunning = false;

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

// --- Backend Process Management ---

function getBackendPath() {
    if (IS_DEV) {
        return null; // In dev mode, use `python main.py`
    }
    const resourcesPath = process.resourcesPath;
    const platform = process.platform;
    const exeName = platform === "win32" ? "vera-server.exe" : "vera-server";
    return path.join(resourcesPath, "backend", exeName);
}

function startBackend() {
    if (backendProcess) return;

    const backendPath = getBackendPath();

    let cmd, args;
    if (backendPath) {
        // Production: bundled executable
        cmd = backendPath;
        args = ["--mode", "server", "--port", String(BACKEND_PORT)];
        console.log(`[Backend] Starting bundled: ${cmd}`);
    } else {
        // Dev mode: run Python directly
        cmd = process.platform === "win32" ? "python" : "python3";
        const mainPy = path.join(__dirname, "..", "main.py");
        args = [mainPy, "--mode", "server", "--port", String(BACKEND_PORT)];
        console.log(`[Backend] Starting dev mode: ${cmd} ${args.join(" ")}`);
    }

    backendProcess = spawn(cmd, args, {
        stdio: ["ignore", "pipe", "pipe"],
        env: {
            ...process.env,
            VERA_ELECTRON: "1",
        },
        cwd: backendPath ? path.dirname(backendPath) : path.join(__dirname, ".."),
    });

    backendProcess.stdout.on("data", (data) => {
        console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr.on("data", (data) => {
        console.error(`[Backend ERR] ${data.toString().trim()}`);
    });

    backendProcess.on("exit", (code, signal) => {
        console.log(`[Backend] Exited with code ${code}, signal ${signal}`);
        backendRunning = false;
        backendProcess = null;

        // Auto-restart if not quitting
        if (!app.isQuitting && code !== 0) {
            console.log("[Backend] Unexpected exit — restarting in 3s...");
            setTimeout(startBackend, 3000);
        }
    });

    backendProcess.on("error", (err) => {
        console.error(`[Backend] Failed to start: ${err.message}`);
        backendProcess = null;

        dialog.showErrorBox(
            "Vera Backend Error",
            `Failed to start the AI backend:\n\n${err.message}\n\nPlease check that the application was installed correctly.`
        );
    });
}

function stopBackend() {
    if (backendProcess) {
        console.log("[Backend] Stopping...");
        if (process.platform === "win32") {
            // On Windows, use taskkill for clean shutdown
            spawn("taskkill", ["/pid", String(backendProcess.pid), "/T", "/F"]);
        } else {
            backendProcess.kill("SIGTERM");
        }

        // Force kill after 5 seconds
        const proc = backendProcess;
        setTimeout(() => {
            if (proc && !proc.killed) {
                console.log("[Backend] Force killing...");
                try {
                    proc.kill("SIGKILL");
                } catch {
                    // Already dead
                }
            }
        }, 5000);

        backendProcess = null;
    }
}

function waitForBackend() {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();

        const check = () => {
            const req = http.get(`${VERA_URL}/health`, (res) => {
                if (res.statusCode === 200) {
                    backendRunning = true;
                    console.log("[Backend] Health check passed ✅");
                    resolve();
                } else {
                    retry();
                }
            });

            req.on("error", () => retry());
            req.setTimeout(2000, () => {
                req.destroy();
                retry();
            });
        };

        const retry = () => {
            if (Date.now() - startTime > HEALTH_CHECK_TIMEOUT) {
                console.error("[Backend] Health check timeout — backend failed to start");
                reject(
                    new Error(
                        "Backend failed to start within 60 seconds. Check logs for errors."
                    )
                );
            } else {
                setTimeout(check, HEALTH_CHECK_INTERVAL);
            }
        };

        check();
    });
}

// --- Splash Screen ---

function createSplashWindow() {
    splashWindow = new BrowserWindow({
        width: 400,
        height: 300,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    const splashHTML = `data:text/html;charset=utf-8,
    <html>
    <head><style>
        body {
            margin: 0; display: flex; align-items: center; justify-content: center;
            height: 100vh; background: rgba(7,11,20,0.95);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: white; flex-direction: column; border-radius: 16px;
            -webkit-app-region: drag;
        }
        .title { font-size: 32px; font-weight: 700; margin-bottom: 8px; }
        .sub { font-size: 14px; opacity: 0.7; margin-bottom: 24px; }
        .spinner {
            width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.1);
            border-top: 3px solid #60a5fa; border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style></head>
    <body>
        <div class="title">🎙️ Vera</div>
        <div class="sub">Starting AI backend...</div>
        <div class="spinner"></div>
    </body>
    </html>`;

    splashWindow.loadURL(splashHTML);
}

// --- Window ---

function createWindow() {
    const bounds = getSetting("windowBounds", { width: 1200, height: 800 });

    mainWindow = new BrowserWindow({
        width: bounds.width,
        height: bounds.height,
        minWidth: 800,
        minHeight: 600,
        title: "Vera",
        icon: getIcon("icon.png"),
        backgroundColor: "#070b14",
        show: false,
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    mainWindow.loadURL(VERA_URL);

    mainWindow.once("ready-to-show", () => {
        if (splashWindow) {
            splashWindow.close();
            splashWindow = null;
        }
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

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: "deny" };
    });

    return mainWindow;
}

// --- IPC Handlers ---

function registerIPC() {
    ipcMain.on("window:minimize", () => {
        if (mainWindow) mainWindow.minimize();
    });

    ipcMain.on("window:maximize", () => {
        if (mainWindow) {
            if (mainWindow.isMaximized()) {
                mainWindow.unmaximize();
            } else {
                mainWindow.maximize();
            }
        }
    });

    ipcMain.on("window:close", () => {
        if (mainWindow) mainWindow.close();
    });

    ipcMain.on("notify", (_event, { title, body }) => {
        showNotification(title, body);
    });

    ipcMain.handle("get-version", () => {
        return app.getVersion();
    });

    ipcMain.handle("get-backend-status", () => {
        return {
            running: backendRunning,
            pid: backendProcess ? backendProcess.pid : null,
            url: VERA_URL,
        };
    });

    ipcMain.handle("restart-backend", async () => {
        stopBackend();
        await new Promise((r) => setTimeout(r, 2000));
        startBackend();
        await waitForBackend();
        return { success: true };
    });
}

// --- Diagram Viewer Window ---

let diagramWindow = null;

function openDiagramWindow() {
    if (diagramWindow && !diagramWindow.isDestroyed()) {
        diagramWindow.show();
        diagramWindow.focus();
        return;
    }

    diagramWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        title: "Vera — Diagram Viewer",
        icon: getIcon("icon.png"),
        backgroundColor: "#070b14",
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    diagramWindow.loadURL(`${VERA_URL}/diagrams`);

    diagramWindow.on("closed", () => {
        diagramWindow = null;
    });
}

// --- Code Viewer Window ---

let codeViewerWindow = null;

function openCodeViewerWindow() {
    if (codeViewerWindow && !codeViewerWindow.isDestroyed()) {
        codeViewerWindow.show();
        codeViewerWindow.focus();
        return;
    }

    codeViewerWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        title: "Vera — Code Viewer",
        icon: getIcon("icon.png"),
        backgroundColor: "#070b14",
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    codeViewerWindow.loadURL(`${VERA_URL}/code-viewer`);

    codeViewerWindow.on("closed", () => {
        codeViewerWindow = null;
    });
}

// --- System Tray ---

function createTray() {
    const icon = getIcon("tray-icon.png") || getIcon("icon.png");
    tray = new Tray(icon);
    tray.setToolTip("Vera — AI Buddy");

    const contextMenu = Menu.buildFromTemplate([
        {
            label: "Show Vera",
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
            label: "📊 Diagram Viewer",
            click: () => openDiagramWindow(),
        },
        {
            label: "👁️ Code Viewer",
            click: () => openCodeViewerWindow(),
        },
        {
            label: "Restart Backend",
            click: async () => {
                stopBackend();
                setTimeout(startBackend, 2000);
            },
        },
        {
            label: "Quit Vera",
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
            title: title || "Vera",
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

app.on("ready", async () => {
    initStore();
    registerIPC();
    createSplashWindow();

    // Start backend and wait for health check
    startBackend();

    try {
        await waitForBackend();
    } catch (err) {
        console.error("[Backend] " + err.message);
        if (splashWindow) {
            splashWindow.close();
            splashWindow = null;
        }
        dialog.showErrorBox(
            "Vera — Backend Failed",
            `The AI backend did not start in time.\n\n${err.message}\n\nThe app will now quit.`
        );
        app.quit();
        return;
    }

    createWindow();
    createTray();
    registerGlobalShortcut();

    if (mainWindow && getSetting("alwaysOnTop", false)) {
        mainWindow.setAlwaysOnTop(true);
    }

    if (getSetting("autoStart", false)) {
        app.setLoginItemSettings({
            openAtLogin: true,
            path: app.getPath("exe"),
        });
    }
});

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        // Minimize to tray
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
    stopBackend();
});

module.exports = { showNotification };
