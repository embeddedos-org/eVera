#!/usr/bin/env python3
"""Master deploy script — builds all eVera platforms.

Usage:
    python deploy.py                    # Build everything for current platform
    python deploy.py --desktop          # Desktop only (Electron + PyInstaller)
    python deploy.py --mobile           # Mobile only (React Native APK/IPA)
    python deploy.py --desktop --mobile # Both
    python deploy.py --platform win     # Electron for specific platform
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SYSTEM = platform.system()


def header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def run(cmd: str | list, cwd: Path = ROOT, check: bool = True) -> int:
    if isinstance(cmd, str):
        print(f"  $ {cmd}")
        result = subprocess.run(cmd, shell=True, cwd=str(cwd))
    else:
        print(f"  $ {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(cwd))
    if check and result.returncode != 0:
        print(f"  ❌ Command failed with exit code {result.returncode}")
    return result.returncode


def check_prereqs() -> dict[str, bool]:
    """Check which build tools are available."""
    prereqs = {}

    # Python + PyInstaller
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, timeout=10)
        prereqs["pyinstaller"] = True
    except Exception:
        prereqs["pyinstaller"] = False

    # Node.js
    try:
        subprocess.run(["node", "--version"], capture_output=True, timeout=10)
        prereqs["node"] = True
    except Exception:
        prereqs["node"] = False

    # npx / electron-builder
    try:
        subprocess.run(["npx", "--version"], capture_output=True, timeout=10)
        prereqs["npx"] = True
    except Exception:
        prereqs["npx"] = False

    # React Native CLI
    try:
        subprocess.run(["npx", "react-native", "--version"], capture_output=True, timeout=10)
        prereqs["react-native"] = True
    except Exception:
        prereqs["react-native"] = False

    # Android SDK (check for ANDROID_HOME)
    import os

    prereqs["android_sdk"] = bool(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"))

    # Xcode (macOS only)
    if SYSTEM == "Darwin":
        try:
            subprocess.run(["xcodebuild", "-version"], capture_output=True, timeout=10)
            prereqs["xcode"] = True
        except Exception:
            prereqs["xcode"] = False
    else:
        prereqs["xcode"] = False

    return prereqs


def build_desktop(plat: str = "current") -> bool:
    """Build the Electron desktop app."""
    header(f"🖥️  Building Desktop App ({plat})")

    # Step 1: Install Electron dependencies
    electron_dir = ROOT / "electron"
    node_modules = electron_dir / "node_modules"
    if not node_modules.exists():
        print("📦 Installing Electron dependencies...")
        if run("npm install", cwd=electron_dir) != 0:
            return False

    # Step 2: Build backend + Electron
    print(f"\n🔨 Building for platform: {plat}")
    build_js = electron_dir / "build.js"
    if run(f"node {build_js} {plat}", cwd=ROOT) != 0:
        return False

    # Step 3: Show output
    dist_dir = electron_dir / "dist"
    if dist_dir.exists():
        installers = (
            list(dist_dir.glob("*.exe"))
            + list(dist_dir.glob("*.dmg"))
            + list(dist_dir.glob("*.AppImage"))
            + list(dist_dir.glob("*.deb"))
        )
        if installers:
            print("\n✅ Desktop installers built:")
            for f in installers:
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"   📦 {f.name} ({size_mb:.1f} MB)")
        else:
            print(f"\n✅ Desktop build complete. Check: {dist_dir}")
    return True


def build_mobile_android() -> bool:
    """Build the React Native Android APK."""
    header("📱 Building Android APK")

    mobile_dir = ROOT / "mobile"
    node_modules = mobile_dir / "node_modules"

    # Step 1: Install dependencies
    if not node_modules.exists():
        print("📦 Installing React Native dependencies...")
        if run("npm install", cwd=mobile_dir) != 0:
            return False

    # Step 2: Build release APK
    android_dir = mobile_dir / "android"
    if not android_dir.exists() or not (android_dir / "gradlew").exists():
        print("⚠️  Android native project not initialized.")
        print("   Run: cd mobile && npx react-native init VeraMobile --template react-native-template-typescript")
        print("   Then copy src/ files into the generated project.")
        print("\n   Alternatively, generate the APK with:")
        print("   cd mobile/android && ./gradlew assembleRelease")
        return False

    gradlew = "gradlew.bat" if SYSTEM == "Windows" else "./gradlew"
    if run(f"{gradlew} assembleRelease", cwd=android_dir) != 0:
        return False

    # Step 3: Show output
    apk_path = android_dir / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    if apk_path.exists():
        size_mb = apk_path.stat().st_size / 1024 / 1024
        print(f"\n✅ Android APK built: {apk_path} ({size_mb:.1f} MB)")
    else:
        print("\n✅ Android build complete. Check: mobile/android/app/build/outputs/apk/")
    return True


def build_mobile_ios() -> bool:
    """Build the React Native iOS IPA."""
    header("🍎 Building iOS IPA")

    if SYSTEM != "Darwin":
        print("⚠️  iOS builds require macOS with Xcode.")
        print("   Transfer the project to a Mac and run:")
        print("   cd mobile/ios && pod install")
        print("   cd mobile && npx react-native run-ios --configuration Release")
        return False

    mobile_dir = ROOT / "mobile"
    ios_dir = mobile_dir / "ios"

    # Install pods
    if (ios_dir / "Podfile").exists():
        print("📦 Installing CocoaPods...")
        if run("pod install", cwd=ios_dir) != 0:
            print("⚠️  pod install failed. Install CocoaPods: gem install cocoapods")
            return False

    # Build archive
    print("🔨 Building iOS archive...")
    if (
        run(
            "xcodebuild -workspace VeraMobile.xcworkspace -scheme VeraMobile "
            "-configuration Release -archivePath build/VeraMobile.xcarchive archive",
            cwd=ios_dir,
        )
        != 0
    ):
        return False

    # Export IPA
    print("📦 Exporting IPA...")
    if (
        run(
            "xcodebuild -exportArchive -archivePath build/VeraMobile.xcarchive "
            "-exportPath build/ipa -exportOptionsPlist ExportOptions.plist",
            cwd=ios_dir,
        )
        != 0
    ):
        print("⚠️  IPA export failed. You may need to configure signing in Xcode.")
        return False

    print("\n✅ iOS IPA built. Check: mobile/ios/build/ipa/")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="eVera Deploy — Build all platforms")
    parser.add_argument("--desktop", action="store_true", help="Build desktop (Electron) installer")
    parser.add_argument("--mobile", action="store_true", help="Build mobile (Android APK + iOS IPA)")
    parser.add_argument("--android-only", action="store_true", help="Build Android APK only")
    parser.add_argument("--ios-only", action="store_true", help="Build iOS IPA only")
    parser.add_argument(
        "--platform",
        default="current",
        choices=["win", "mac", "linux", "all", "current"],
        help="Desktop platform target",
    )
    parser.add_argument("--skip-prereq-check", action="store_true", help="Skip prerequisite check")
    args = parser.parse_args()

    # Default: build everything
    build_all = not (args.desktop or args.mobile or args.android_only or args.ios_only)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  🚀 eVera Deploy v0.5.0                                ║
║  System: {SYSTEM:<49}║
║  Desktop: {"Yes" if (build_all or args.desktop) else "No":<48}║
║  Mobile:  {"Yes" if (build_all or args.mobile) else "No":<48}║
╚══════════════════════════════════════════════════════════╝
""")

    # Check prerequisites
    if not args.skip_prereq_check:
        header("🔍 Checking Prerequisites")
        prereqs = check_prereqs()
        for name, available in prereqs.items():
            icon = "✅" if available else "❌"
            print(f"  {icon} {name}")
        print()

    results = {}

    # Desktop build
    if build_all or args.desktop:
        results["desktop"] = build_desktop(args.platform)

    # Mobile builds
    if build_all or args.mobile or args.android_only:
        results["android"] = build_mobile_android()

    if build_all or args.mobile or args.ios_only:
        results["ios"] = build_mobile_ios()

    # Summary
    header("📊 Build Summary")
    for target, success in results.items():
        icon = "✅" if success else "❌"
        print(f"  {icon} {target}")

    if all(results.values()):
        print("\n🎉 All builds completed successfully!")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"\n⚠️  Some builds failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
