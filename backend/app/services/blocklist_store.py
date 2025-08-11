from __future__ import annotations

import json
import os
from typing import List, Set

from ..utils.paths import get_app_data_dir


class BlocklistStore:
    def __init__(self) -> None:
        self._dir = get_app_data_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, "blocked_ips.json")

    def _read(self) -> Set[str]:
        try:
            if not os.path.exists(self._file):
                return set()
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data or [])
        except Exception:
            return set()

    def _write(self, ips: Set[str]) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(sorted(list(ips)), f)
        os.chmod(self._file, 0o600)

    def list(self) -> List[str]:
        return sorted(list(self._read()))

    def add(self, ip: str) -> None:
        ips = self._read()
        if ip not in ips:
            ips.add(ip)
            self._write(ips)

    def remove(self, ip: str) -> None:
        ips = self._read()
        if ip in ips:
            ips.remove(ip)
            self._write(ips)


blocklist_store = BlocklistStore()


