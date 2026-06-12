from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class CredentialType(str, Enum):
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    BASIC_AUTH = "basic_auth"
    BEARER_TOKEN = "bearer_token"
    CUSTOM = "custom"
    MATRIX_ACCESS = "matrix_access"
    MINIO_S3 = "minio_s3"


@dataclass
class Credential:
    key: str
    value: str
    cred_type: CredentialType = CredentialType.API_KEY
    provider: str = ""
    description: str = ""
    expires_at: float = 0.0
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "cred_type": self.cred_type.value,
            "provider": self.provider,
            "description": self.description,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def safe_dict(self) -> dict:
        d = self.to_dict()
        d["value"] = self.value[:8] + "..." if len(self.value) > 8 else "***"
        return d


class CredentialVault:
    def __init__(self, storage_path: Optional[str] = None, use_encryption: bool = True):
        self._credentials: dict[str, Credential] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._use_encryption = use_encryption
        self._fernet = None

        if self._use_encryption:
            self._init_encryption()

        if self._storage_path and self._storage_path.exists():
            self._load()

    def _init_encryption(self):
        try:
            from cryptography.fernet import Fernet

            key_file = (
                self._storage_path.parent / ".cogu_key"
                if self._storage_path
                else Path.home() / ".cogu" / ".cogu_key"
            )

            if key_file.exists():
                with open(key_file, "rb") as f:
                    key = f.read()
            else:
                key = Fernet.generate_key()
                key_file.parent.mkdir(parents=True, exist_ok=True)
                with open(key_file, "wb") as f:
                    f.write(key)

            self._fernet = Fernet(key)
        except ImportError:
            self._use_encryption = False

    def set(self, key: str, value: str, cred_type: CredentialType = CredentialType.API_KEY,
            provider: str = "", description: str = "", expires_at: float = 0.0,
            metadata: dict = None) -> Credential:
        cred = Credential(
            key=key,
            value=value,
            cred_type=cred_type,
            provider=provider,
            description=description,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        self._credentials[key] = cred
        if self._storage_path:
            self._save()
        return cred

    def get(self, key: str) -> Optional[Credential]:
        cred = self._credentials.get(key)
        if cred and cred.is_expired:
            self.delete(key)
            return None
        return cred

    def get_value(self, key: str, default: Any = None) -> Any:
        cred = self.get(key)
        return cred.value if cred else default

    def delete(self, key: str) -> bool:
        if key in self._credentials:
            del self._credentials[key]
            if self._storage_path:
                self._save()
            return True
        return False

    def list(self) -> list[Credential]:
        return [c for c in self._credentials.values() if not c.is_expired]

    def list_by_provider(self, provider: str) -> list[Credential]:
        return [c for c in self._credentials.values()
                if c.provider == provider and not c.is_expired]

    def list_by_type(self, cred_type: CredentialType) -> list[Credential]:
        return [c for c in self._credentials.values()
                if c.cred_type == cred_type and not c.is_expired]

    def _save(self):
        if not self._storage_path:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        for key, cred in self._credentials.items():
            entry = cred.to_dict()
            value = cred.value
            if self._use_encryption and self._fernet:
                value = self._fernet.encrypt(value.encode()).decode()
            entry["value"] = value
            entry["encrypted"] = self._use_encryption
            data[key] = entry

        tmp_path = self._storage_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._storage_path)

    def _load(self):
        try:
            with open(self._storage_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        for key, entry in data.items():
            value = entry.get("value", "")
            if entry.get("encrypted") and self._fernet:
                try:
                    value = self._fernet.decrypt(value.encode()).decode()
                except Exception:
                    continue

            self._credentials[key] = Credential(
                key=key,
                value=value,
                cred_type=CredentialType(entry.get("cred_type", "api_key")),
                provider=entry.get("provider", ""),
                description=entry.get("description", ""),
                expires_at=entry.get("expires_at", 0.0),
                metadata=entry.get("metadata", {}),
                created_at=entry.get("created_at", time.time()),
            )
