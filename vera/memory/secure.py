"""Secure vault — encrypted storage for sensitive data."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SecureVault:
    """Fernet-encrypted key-value store for passwords, API keys, PII."""

    def __init__(self, vault_path: Path | None = None, key: bytes | None = None) -> None:
        self._vault_path = vault_path
        self._fernet = None
        self._data: dict[str, str] = {}
        self._init_encryption(key)
        if vault_path and vault_path.exists():
            self._load()

    def _init_encryption(self, key: bytes | None) -> None:
        try:
            from cryptography.fernet import Fernet

            if key:
                self._fernet = Fernet(key)
            else:
                # Generate or load key
                key_path = self._vault_path.with_suffix(".key") if self._vault_path else None
                if key_path and key_path.exists():
                    stored_key = key_path.read_bytes()
                    self._fernet = Fernet(stored_key)
                else:
                    new_key = Fernet.generate_key()
                    self._fernet = Fernet(new_key)
                    if key_path:
                        key_path.parent.mkdir(parents=True, exist_ok=True)
                        key_path.write_bytes(new_key)
                        logger.info("Generated new vault key at %s", key_path)
        except ImportError:
            logger.critical(
                "cryptography package not installed — SecureVault running in PLAINTEXT mode! "
                "Install with: pip install cryptography"
            )

    def store(self, key: str, value: str) -> None:
        self._data[key] = value
        self._save()
        logger.debug("Stored secure value for key: %s", key)

    def retrieve(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def _save(self) -> None:
        if not self._vault_path:
            return
        self._vault_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(self._data).encode()
        if self._fernet:
            encrypted = self._fernet.encrypt(raw)
            self._vault_path.write_bytes(encrypted)
        else:
            self._vault_path.write_bytes(raw)

    def _load(self) -> None:
        if not self._vault_path or not self._vault_path.exists():
            return
        raw = self._vault_path.read_bytes()
        try:
            if self._fernet:
                decrypted = self._fernet.decrypt(raw)
                self._data = json.loads(decrypted)
            else:
                self._data = json.loads(raw)
            logger.info("Loaded %d entries from secure vault", len(self._data))
        except Exception:
            logger.error("Failed to decrypt vault at %s — starting fresh", self._vault_path)
            self._data = {}
