from __future__ import annotations

import base64
import json
import os
from typing import Optional

from cryptography.fernet import Fernet

from ..config import settings
from ..utils.paths import get_app_data_dir


SETTINGS_FILE = "settings.json"
SECRET_FILE = "secret.key"


class SettingsStore:
    def __init__(self) -> None:
        self._dir = get_app_data_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, SETTINGS_FILE)
        self._secret_path = os.path.join(self._dir, SECRET_FILE)
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if settings.secret_key:
            key = settings.secret_key.encode()
            # Expect base64 32-byte urlsafe key; if not, derive simple padded
            try:
                base64.urlsafe_b64decode(key)
                return key
            except Exception:
                # Derive from provided string
                try:
                    raw = settings.secret_key.encode()
                    padded = base64.urlsafe_b64encode(raw.ljust(32, b'0')[:32])
                    return padded
                except Exception:
                    pass
        if os.path.exists(self._secret_path):
            with open(self._secret_path, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(self._secret_path, "wb") as f:
            f.write(key)
        os.chmod(self._secret_path, 0o600)
        return key

    def _read_json(self) -> dict:
        if not os.path.exists(self._file):
            return {}
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_json(self, data: dict) -> None:
        tmp = self._file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self._file)
        os.chmod(self._file, 0o600)

    def set_openai_api_key(self, plaintext: str) -> None:
        token = self._fernet.encrypt(plaintext.encode()).decode()
        data = self._read_json()
        data["openai_api_key_enc"] = token
        self._write_json(data)

    def get_openai_api_key(self) -> Optional[str]:
        data = self._read_json()
        token = data.get("openai_api_key_enc")
        if not token:
            return settings.openai_api_key
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except Exception:
            return None

    def has_openai_key(self) -> bool:
        return bool(self.get_openai_api_key())


settings_store = SettingsStore()


