from __future__ import annotations

import os
from ..config import settings


def get_app_data_dir() -> str:
    desired = settings.app_data_dir
    try:
        os.makedirs(desired, exist_ok=True)
        # Try write test
        test_path = os.path.join(desired, ".wtest")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)
        return desired
    except Exception:
        # Fallback to home directory
        home_fallback = os.path.expanduser("~/.routergeist/data")
        os.makedirs(home_fallback, exist_ok=True)
        return home_fallback


