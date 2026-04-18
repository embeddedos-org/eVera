/**
 * Voca Desktop — Build Script
 *
 * Packages the Electron app for distribution.
 * Usage: node build.js [win|mac|linux|all]
 */

const { execSync } = require("child_process");
const path = require("path");

const platform = process.argv[2] || "current";

const commands = {
    win: "npx electron-builder --win --x64",
    mac: "npx electron-builder --mac --x64 --arm64",
    linux: "npx electron-builder --linux --x64",
    all: "npx electron-builder --win --mac --linux",
    current: "npx electron-builder",
};

const cmd = commands[platform] || commands.current;

console.log(`\n🔨 Building Voca Desktop for: ${platform}\n`);
console.log(`Running: ${cmd}\n`);

try {
    execSync(cmd, {
        cwd: __dirname,
        stdio: "inherit",
        env: { ...process.env },
    });
    console.log("\n✅ Build complete! Check the dist/ directory.\n");
} catch (error) {
    console.error("\n❌ Build failed:", error.message);
    process.exit(1);
}
