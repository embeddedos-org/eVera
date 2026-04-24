# -*- mode: python ; coding: utf-8 -*-
"""Vera PyInstaller spec — bundles the Python backend into a distributable."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH)

# Collect litellm and tiktoken fully (they discover providers/encodings at runtime)
litellm_datas, litellm_binaries, litellm_hiddenimports = collect_all("litellm")
tiktoken_datas, tiktoken_binaries, tiktoken_hiddenimports = collect_all("tiktoken")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=litellm_binaries + tiktoken_binaries,
    datas=[
        (str(ROOT / "vera" / "static"), "vera/static"),
        (str(ROOT / "config.py"), "."),
        (str(ROOT / ".env.example"), "."),
        # Bundle data skeleton for first-run
        (str(ROOT / "data"), "data"),
    ]
    + litellm_datas
    + tiktoken_datas,
    hiddenimports=[
        # --- LiteLLM & LLM providers ---
        "litellm",
        "litellm.llms",
        *litellm_hiddenimports,
        # --- Tiktoken (tokenizer) ---
        "tiktoken",
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        *tiktoken_hiddenimports,
        # --- Sentence transformers / FAISS ---
        "sentence_transformers",
        "faiss",
        # --- Web framework ---
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
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "websockets",
        "httpx",
        # --- LangChain / LangGraph ---
        "langchain_core",
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.state",
        # --- Voice / TTS / STT ---
        "pyttsx3",
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        "edge_tts",
        # --- Image / Vision ---
        "PIL",
        "PIL.Image",
        # --- Browser automation ---
        "playwright",
        "playwright.sync_api",
        "playwright.async_api",
        # --- Security ---
        "cryptography",
        "cryptography.fernet",
        # --- Utilities ---
        "duckduckgo_search",
        "beautifulsoup4",
        "bs4",
        "yfinance",
        "pyautogui",
        "psutil",
        "pyperclip",
        "chardet",
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
    name="vera-server",
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
    name="vera-server",
)
