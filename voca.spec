# -*- mode: python ; coding: utf-8 -*-
"""Voca PyInstaller spec — bundles the Python backend into a distributable."""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "voca" / "static"), "voca/static"),
        (str(ROOT / "config.py"), "."),
        (str(ROOT / ".env.example"), "."),
    ],
    hiddenimports=[
        "litellm",
        "litellm.llms",
        "sentence_transformers",
        "faiss",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "langchain_core",
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.state",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "websockets",
        "httpx",
        "cryptography",
        "cryptography.fernet",
        "duckduckgo_search",
        "beautifulsoup4",
        "bs4",
        "yfinance",
        "pyautogui",
        "psutil",
        "pyperclip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "jupyter",
        "notebook",
        "IPython",
        "pytest",
        "ruff",
        "bandit",
        "safety",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voca-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="voca-server",
)
