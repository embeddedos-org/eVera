#!/usr/bin/env python3
"""Vera Setup Script — installs all dependencies and configures the environment.

Usage:
    python setup_vera.py          # Full install
    python setup_vera.py --minimal  # Core only (no browser/trading)
    python setup_vera.py --check    # Check what's installed
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


def run(cmd, check=False, capture=False):
    """Run a command and return result."""
    print(f"  → {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, check=check,
            capture_output=capture, text=True,
            timeout=300,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Command failed: {e}")
        return None
    except subprocess.TimeoutExpired:
        print("  ⚠ Command timed out")
        return None


def get_python():
    """Find the best Python executable."""
    for py in ["python3.12", "python3.11", "python3", "python", "py -3"]:
        result = run(f"{py} --version", capture=True)
        if result and result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print(f"  Found: {version}")
            return py
    return None


def check_version(python):
    """Check Python version is 3.11+."""
    result = run(f"{python} -c \"import sys; print(sys.version_info[:2])\"", capture=True)
    if result and result.returncode == 0:
        version = eval(result.stdout.strip())
        if version >= (3, 11):
            return True
        print(f"  ⚠ Python {version[0]}.{version[1]} found but 3.11+ required")
    return False


def install_python_if_needed():
    """Install Python 3.12 if not available."""
    system = platform.system()

    if system == "Linux":
        print("\n📦 Installing Python 3.12...")
        run("sudo apt update")
        run("sudo apt install -y software-properties-common")
        run("sudo add-apt-repository -y ppa:deadsnakes/ppa")
        run("sudo apt update")
        run("sudo apt install -y python3.12 python3.12-venv python3.12-dev")
        return "python3.12"

    elif system == "Darwin":
        print("\n📦 Installing Python via Homebrew...")
        run("brew install python@3.12")
        return "python3.12"

    elif system == "Windows":
        print("\n⚠ Please install Python 3.12 from https://www.python.org/downloads/")
        print("  Make sure to check 'Add Python to PATH' during installation")
        return None

    return None


def create_venv(python):
    """Create virtual environment."""
    venv_path = Path(".venv")
    if venv_path.exists():
        print("  Virtual environment already exists")
        return True

    result = run(f"{python} -m venv .venv")
    return result is not None and (venv_path / ("Scripts" if platform.system() == "Windows" else "bin")).exists()


def get_pip():
    """Get the pip command for the virtual environment."""
    system = platform.system()
    if system == "Windows":
        pip = str(Path(".venv/Scripts/pip.exe"))
        python = str(Path(".venv/Scripts/python.exe"))
    else:
        pip = str(Path(".venv/bin/pip"))
        python = str(Path(".venv/bin/python"))

    if Path(pip).exists():
        return pip, python
    return None, None


def install_core(pip):
    """Install core dependencies."""
    print("\n📦 Installing core dependencies...")
    run(f"{pip} install --upgrade pip setuptools wheel")

    # Install one by one to handle failures gracefully
    core_deps = [
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "websockets>=12.0",
        "litellm>=1.0.0",
        "httpx>=0.27.0",
        "cryptography>=41.0",
    ]

    failed = []
    for dep in core_deps:
        result = run(f"{pip} install \"{dep}\"")
        if result is None or result.returncode != 0:
            failed.append(dep)

    return failed


def install_langgraph(pip):
    """Install LangGraph — try multiple versions."""
    print("\n📦 Installing LangGraph...")
    for version in ["langgraph==0.2.0", "langgraph==0.1.0", "langgraph==0.0.8", "langgraph"]:
        result = run(f"{pip} install \"{version}\"", capture=True)
        if result and result.returncode == 0:
            print(f"  ✅ Installed {version}")
            return True

    print("  ⚠ LangGraph failed — trying langchain only")
    run(f"{pip} install langchain-core>=0.1.0")
    return False


def install_memory(pip):
    """Install memory dependencies (FAISS, sentence-transformers)."""
    print("\n📦 Installing memory dependencies...")
    run(f"{pip} install faiss-cpu>=1.7.0")
    run(f"{pip} install sentence-transformers>=2.0.0")


def install_search(pip):
    """Install web search dependencies."""
    print("\n📦 Installing search dependencies...")
    run(f"{pip} install duckduckgo-search>=5.0")
    run(f"{pip} install beautifulsoup4>=4.12.0")


def install_trading(pip):
    """Install stock trading dependencies."""
    print("\n📦 Installing trading dependencies...")
    run(f"{pip} install yfinance>=0.2.30")
    # Optional broker APIs
    run(f"{pip} install alpaca-trade-api>=3.0")


def install_browser(pip):
    """Install browser automation dependencies."""
    print("\n📦 Installing browser automation...")
    result = run(f"{pip} install playwright>=1.40.0")
    if result and result.returncode == 0:
        print("  Installing Chromium browser...")
        venv_python = str(Path(".venv/Scripts/python.exe")) if platform.system() == "Windows" else str(Path(".venv/bin/python"))
        run(f"{venv_python} -m playwright install chromium")


def install_dev(pip):
    """Install development dependencies."""
    print("\n📦 Installing dev dependencies...")
    run(f"{pip} install pytest>=8.0 pytest-asyncio>=0.23 pytest-cov>=4.0 ruff>=0.3")


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    if not Path(".env").exists() and Path(".env.example").exists():
        print("\n📄 Creating .env from .env.example...")
        import shutil
        shutil.copy(".env.example", ".env")
        print("  ✅ Created .env — edit it with your API keys")
    elif not Path(".env").exists():
        print("\n📄 Creating minimal .env...")
        Path(".env").write_text(
            "# Vera Configuration\n"
            "VERA_LLM_OLLAMA_URL=http://localhost:11434\n"
            "VERA_LLM_OLLAMA_MODEL=llama3.2\n"
            "VERA_SERVER_HOST=127.0.0.1\n"
            "VERA_SERVER_PORT=8000\n",
            encoding="utf-8",
        )


def create_data_dirs():
    """Create required data directories."""
    dirs = [
        "data", "data/faiss_index", "data/browser_sessions",
        "data/rbac", "data/workflows", "plugins",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("  ✅ Data directories created")


def configure_system_for_247():
    """Configure the system for 24/7 operation."""
    system = platform.system()

    if system == "Windows":
        print("\n⚡ Configuring Windows for 24/7 operation...")

        # Disable sleep/hibernate on AC power
        run('powershell -Command "powercfg /change standby-timeout-ac 0"')
        run('powershell -Command "powercfg /change hibernate-timeout-ac 0"')
        run('powershell -Command "powercfg /change monitor-timeout-ac 0"')
        print("  ✅ Disabled sleep, hibernate, and monitor timeout on AC power")

        # Create a startup batch script
        startup_script = Path("start_vera.bat")
        venv_python = Path(".venv/Scripts/python.exe").resolve()
        main_py = Path("main.py").resolve()
        work_dir = Path(".").resolve()
        port = 8000

        startup_script.write_text(
            f'@echo off\n'
            f'cd /d "{work_dir}"\n'
            f'echo Starting Vera AI Buddy...\n'
            f'start "" "http://localhost:{port}"\n'
            f'timeout /t 3 >nul\n'
            f'"{venv_python}" "{main_py}" --mode server\n',
            encoding="utf-8",
        )
        print("  ✅ Created start_vera.bat (auto-opens browser)")

        # Add to Windows Task Scheduler for auto-start on boot
        task_xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Settings>
    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
  </Settings>
  <Actions>
    <Exec>
      <Command>{venv_python}</Command>
      <Arguments>{main_py} --mode server</Arguments>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''
        task_file = Path("vera_task.xml")
        task_file.write_text(task_xml, encoding="utf-16")
        result = run(f'schtasks /create /tn "VeraServer" /xml "{task_file}" /f')
        if result and result.returncode == 0:
            print("  ✅ Added to Task Scheduler — Vera starts on boot and auto-restarts on crash")
        else:
            print("  ⚠ Task Scheduler setup needs admin — run setup as Administrator for auto-start")
        task_file.unlink(missing_ok=True)

    elif system == "Linux":
        print("\n⚡ Configuring Linux for 24/7 operation...")
        venv_python = Path(".venv/bin/python").resolve()
        main_py = Path("main.py").resolve()
        work_dir = Path(".").resolve()
        user = os.environ.get("USER", "root")

        service = f"""[Unit]
Description=Vera AI Buddy
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={work_dir}
ExecStart={venv_python} {main_py} --mode server
Restart=always
RestartSec=5
Environment=PATH={Path('.venv/bin').resolve()}:/usr/bin

[Install]
WantedBy=multi-user.target
"""
        service_path = Path("/etc/systemd/system/vera.service")
        try:
            service_path.write_text(service)
            run("sudo systemctl daemon-reload")
            run("sudo systemctl enable vera")
            run("sudo systemctl start vera")
            print("  ✅ Created systemd service — Vera runs 24/7 and auto-restarts")
        except PermissionError:
            print("  ⚠ Need sudo. Run: sudo cp vera.service /etc/systemd/system/")
            Path("vera.service").write_text(service)

    elif system == "Darwin":
        print("\n⚡ Configuring macOS for 24/7 operation...")
        # Disable sleep
        run("sudo pmset -a disablesleep 1")
        print("  ✅ Disabled macOS sleep")

        # Create launchd plist
        venv_python = str(Path(".venv/bin/python").resolve())
        main_py = str(Path("main.py").resolve())
        work_dir = str(Path(".").resolve())

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.vera.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>{venv_python}</string>
        <string>{main_py}</string>
        <string>--mode</string>
        <string>server</string>
    </array>
    <key>WorkingDirectory</key><string>{work_dir}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>"""
        plist_path = Path.home() / "Library/LaunchAgents/com.vera.server.plist"
        plist_path.write_text(plist)
        run(f"launchctl load {plist_path}")
        print("  ✅ Created launchd service — Vera runs 24/7 and auto-restarts")


def check_install(pip):
    """Verify installation."""
    print("\n🔍 Checking installation...")
    venv_python = str(Path(".venv/Scripts/python.exe")) if platform.system() == "Windows" else str(Path(".venv/bin/python"))

    checks = {
        "FastAPI": "import fastapi",
        "Uvicorn": "import uvicorn",
        "LiteLLM": "import litellm",
        "Pydantic": "import pydantic",
        "HTTPX": "import httpx",
        "Cryptography": "import cryptography",
        "DuckDuckGo": "import duckduckgo_search",
        "BeautifulSoup": "import bs4",
        "yfinance": "import yfinance",
        "FAISS": "import faiss",
        "Sentence-Transformers": "import sentence_transformers",
        "Playwright": "import playwright",
        "Ruff": "import ruff",
        "Pytest": "import pytest",
    }

    results = {}
    for name, import_stmt in checks.items():
        result = run(f"{venv_python} -c \"{import_stmt}\"", capture=True)
        ok = result is not None and result.returncode == 0
        results[name] = ok
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    return results


def main():
    minimal = "--minimal" in sys.argv
    check_only = "--check" in sys.argv

    print("""
╔══════════════════════════════════════╗
║   🎙️ Vera Setup Script v0.4.0       ║
║   Installing all dependencies...     ║
╚══════════════════════════════════════╝
""")

    # Step 1: Find Python
    print("🐍 Finding Python...")
    python = get_python()
    if not python:
        python = install_python_if_needed()
        if not python:
            print("\n❌ Python not found. Install Python 3.11+ and try again.")
            sys.exit(1)

    if not check_version(python):
        print("  Trying to install Python 3.12...")
        python = install_python_if_needed()
        if not python:
            print("\n❌ Python 3.11+ required. Please install it manually.")
            sys.exit(1)

    # Step 2: Create virtual environment
    print("\n📁 Setting up virtual environment...")
    if not create_venv(python):
        print("❌ Failed to create virtual environment")
        sys.exit(1)

    pip, venv_python = get_pip()
    if not pip:
        print("❌ pip not found in virtual environment")
        sys.exit(1)

    if check_only:
        check_install(pip)
        return

    # Step 3: Install dependencies
    failed = install_core(pip)
    if failed:
        print(f"\n⚠ Failed to install: {failed}")

    install_langgraph(pip)
    install_memory(pip)
    install_search(pip)

    if not minimal:
        install_trading(pip)
        install_browser(pip)

    install_dev(pip)

    # Step 4: Setup
    create_env_file()
    create_data_dirs()
    configure_system_for_247()

    # Step 5: Verify
    results = check_install(pip)

    # Summary
    installed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"""
╔══════════════════════════════════════╗
║   ✅ Setup Complete!                 ║
║   {installed}/{total} packages installed             ║
╚══════════════════════════════════════╝

To activate the environment:
""")

    if platform.system() == "Windows":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")

    print("""
To run Vera:
  python main.py --mode server

Then open: http://localhost:8000
""")


if __name__ == "__main__":
    main()
