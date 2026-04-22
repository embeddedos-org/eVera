/**
 * Vera Desktop — Build Script
 *
 * Builds the Python backend via PyInstaller, then packages with electron-builder.
 * Usage:
 *   node build.js [win|mac|linux|all]
 *   node build.js --skip-backend win      # Skip backend build
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const args = process.argv.slice(2);
const skipBackend = args.includes("--skip-backend");
const platformArg = args.find((a) => !a.startsWith("--")) || "current";

const ROOT = path.join(__dirname, "..");
const DIST_BACKEND = path.join(ROOT, "dist", "vera-server");

const electronCommands = {
    win: "npx electron-builder --win --x64",
    mac: "npx electron-builder --mac --x64 --arm64",
    linux: "npx electron-builder --linux --x64",
    all: "npx electron-builder --win --mac --linux",
    current: "npx electron-builder",
};

function buildBackend() {
    console.log("\n🐍 Step 1: Building Python backend with PyInstaller...\n");

    const python = process.platform === "win32" ? "python" : "python3";
    const buildScript = path.join(ROOT, "build_backend.py");

    try {
        execSync(`${python} ${buildScript} --clean`, {
            cwd: ROOT,
            stdio: "inherit",
        });
    } catch (error) {
        console.error("\n❌ Backend build failed:", error.message);
        process.exit(1);
    }

    if (!fs.existsSync(DIST_BACKEND)) {
        console.error(`\n❌ Backend output not found at ${DIST_BACKEND}`);
        process.exit(1);
    }

    console.log("✅ Backend build complete\n");
}

function buildElectron() {
    const cmd = electronCommands[platformArg] || electronCommands.current;

    console.log(`\n📦 Step 2: Packaging Electron app for: ${platformArg}\n`);
    console.log(`Running: ${cmd}\n`);

    try {
        execSync(cmd, {
            cwd: __dirname,
            stdio: "inherit",
            env: { ...process.env },
        });
        console.log("\n✅ Electron build complete! Check electron/dist/\n");
    } catch (error) {
        console.error("\n❌ Electron build failed:", error.message);
        process.exit(1);
    }
}

// --- Main ---

console.log(`
╔══════════════════════════════════════════╗
║  🔨 Vera Desktop Builder v0.5.0        ║
║  Platform: ${platformArg.padEnd(30)}║
║  Skip backend: ${String(skipBackend).padEnd(25)}║
╚══════════════════════════════════════════╝
`);

if (!skipBackend) {
    buildBackend();
} else {
    if (!fs.existsSync(DIST_BACKEND)) {
        console.warn("⚠️  --skip-backend used but backend not found. Building anyway...");
        buildBackend();
    } else {
        console.log("⏭️  Skipping backend build (--skip-backend)\n");
    }
}

buildElectron();
