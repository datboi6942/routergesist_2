from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import bcrypt

from ..config import settings
from ..utils.paths import get_app_data_dir


ADMIN_FILE = "admin.json"


@dataclass
class AdminCreds:
    username: str
    password_hash: str


class CredentialStore:
    def __init__(self) -> None:
        self._dir = get_app_data_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._path = os.path.join(self._dir, ADMIN_FILE)

    def get_admin(self) -> Optional[AdminCreds]:
        # Env overrides
        if settings.admin_username and settings.admin_password_hash:
            return AdminCreds(settings.admin_username, settings.admin_password_hash)
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("username") or not data.get("password_hash"):
                return None
            return AdminCreds(data["username"], data["password_hash"])
        except Exception:
            return None

    def set_admin(self, username: str, password_plain: str) -> None:
        hashed = bcrypt.hashpw(password_plain.encode(), bcrypt.gensalt()).decode()
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"username": username, "password_hash": hashed}, f)
        os.chmod(self._path, 0o600)

    def update_password(self, new_password_plain: str) -> None:
        admin = self.get_admin()
        if not admin:
            raise ValueError("Admin not initialized")
        hashed = bcrypt.hashpw(new_password_plain.encode(), bcrypt.gensalt()).decode()
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"username": admin.username, "password_hash": hashed}, f)
        os.chmod(self._path, 0o600)

    @staticmethod
    def verify(password_plain: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password_plain.encode(), password_hash.encode())
        except Exception:
            return False

    def has_admin(self) -> bool:
        return self.get_admin() is not None


credential_store = CredentialStore()


