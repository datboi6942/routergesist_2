from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import List

from ..config import settings


SAFE_PATHS = [
    lambda: settings.app_data_dir,
    lambda: "/opt/routergeist/run",
    lambda: "/var/log/routergeist",
]


def _shred_path(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        subprocess.run(["shred", "-zuf", path], check=False)
    except Exception:
        # Fallback: overwrite if regular file
        if os.path.isfile(path):
            try:
                size = os.path.getsize(path)
                with open(path, "r+b", buffering=0) as f:
                    f.write(os.urandom(size))
                os.remove(path)
            except Exception:
                pass


def _wipe_directory(directory: str) -> None:
    if not os.path.exists(directory):
        return
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in files:
            _shred_path(os.path.join(root, name))
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except Exception:
                pass
    try:
        os.rmdir(directory)
    except Exception:
        pass


def nuke(full_device: bool = False) -> str:
    if not settings.nucleus_unlock:
        return "Nuke is locked by server policy"

    if full_device and not settings.allow_full_device_wipe:
        full_device = False

    # Wipe safe app-scoped paths
    for fn in SAFE_PATHS:
        try:
            path = fn()
            _wipe_directory(path)
        except Exception:
            pass

    if full_device:
        # Call privileged script (must be allowed in sudoers) for device wipe
        try:
            subprocess.Popen(
                ["sudo", "/bin/bash", "/opt/routergeist/scripts/privileged/nuke.sh", "--full"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "Full device wipe initiated"
        except Exception:
            return "Failed to start full device wipe"

    return "Application data wiped"


