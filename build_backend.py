#!/usr/bin/env python3
"""Build script — bundles the Voca Python backend via PyInstaller.

Usage:
    python build_backend.py              # Build for current platform
    python build_backend.py --clean      # Clean previous builds first
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist" / "voca-server"
DATA_TEMPLATE_DIR = ROOT / "data"
ENV_EXAMPLE = ROOT / ".env.example"

SYSTEM = platform.system()
EXE_NAME = "voca-server.exe" if SYSTEM == "Windows" else "voca-server"


def clean() -> None:
    """Remove previous build artifacts."""
    for d in ["build", "dist"]:
        p = ROOT / d
        if p.exists():
            print(f"🧹 Removing {p}")
            shutil.rmtree(p)


def build() -> None:
    """Run PyInstaller with the spec file."""
    spec = ROOT / "voca.spec"
    if not spec.exists():
        print("❌ voca.spec not found — run from the project root")
        sys.exit(1)

    print("🔨 Running PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("❌ PyInstaller build failed")
        sys.exit(1)


def copy_data() -> None:
    """Copy data/ template and .env.example alongside the built executable."""
    if DATA_TEMPLATE_DIR.exists():
        dest = DIST_DIR / "data"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(DATA_TEMPLATE_DIR), str(dest))
        print(f"📂 Copied data/ → {dest}")

    if ENV_EXAMPLE.exists():
        dest = DIST_DIR / ".env.example"
        shutil.copy2(str(ENV_EXAMPLE), str(dest))
        print(f"📄 Copied .env.example → {dest}")


def validate() -> None:
    """Quick smoke test: run the built executable with --help."""
    exe = DIST_DIR / EXE_NAME
    if not exe.exists():
        print(f"⚠️  Built executable not found at {exe}")
        return

    print(f"✅ Built executable: {exe}")
    print(f"📦 Bundle size: {sum(f.stat().st_size for f in DIST_DIR.rglob('*') if f.is_file()) / 1024 / 1024:.1f} MB")

    try:
        result = subprocess.run(
            [str(exe), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print("✅ Executable runs successfully")
        else:
            print(f"⚠️  Executable returned code {result.returncode}")
            if result.stderr:
                print(f"   stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("⚠️  Executable timed out (may be normal for server startup)")
    except Exception as e:
        print(f"⚠️  Could not validate executable: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Voca backend with PyInstaller")
    parser.add_argument("--clean", action="store_true", help="Clean previous builds first")
    args = parser.parse_args()

    print(f"""
===========================================
  Voca Backend Builder v0.5.1
  Platform: {SYSTEM}
===========================================
""")

    if args.clean:
        clean()

    build()
    copy_data()
    validate()

    print(f"""
Done! Backend build complete.
   Output: {DIST_DIR}
   Executable: {DIST_DIR / EXE_NAME}

Next: cd electron && npm run build
""")


if __name__ == "__main__":
    main()
