from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, Any

from .router_config_store import router_config_store
from ..utils.paths import get_app_data_dir
from pathlib import Path


def apply_router_config() -> str:
    cfg: Dict[str, Any] = router_config_store.load()
    # Auto-detect Wi‑Fi AP interface if configured one is missing. Prefer any wireless iface not equal to WAN iface.
    try:
        wan_if = cfg.get("wan", {}).get("interface")
        wifi_if = cfg.get("wifi", {}).get("interface")

        def is_wireless(name: str) -> bool:
            return os.path.exists(f"/sys/class/net/{name}/wireless")

        # Collect system interfaces
        ip_output = subprocess.check_output(["ip", "-j", "addr"], text=True)
        data = json.loads(ip_output)
        system_ifaces = [e.get("ifname") for e in data if e.get("ifname") and e.get("ifname") != "lo"]

        # Build candidate list: any wireless iface not equal to WAN
        candidates = [n for n in system_ifaces if is_wireless(n) and (not wan_if or n != wan_if)]

        # If wifi_if is missing/invalid, or equals WAN, prefer a different wireless iface
        needs_switch = (
            not wifi_if
            or wifi_if not in system_ifaces
            or not is_wireless(wifi_if)
            or (wan_if and wifi_if == wan_if)
        )
        if needs_switch and candidates:
            cfg.setdefault("wifi", {})["interface"] = candidates[0]
            # Persist so UI reflects actual device
            try:
                router_config_store.save(cfg)
            except Exception:
                pass
    except Exception:
        pass
    run_dir = os.path.join(get_app_data_dir(), "run")
    os.makedirs(run_dir, exist_ok=True)
    cfg_path = os.path.join(run_dir, "router_config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    # Resolve script path: prefer project-local script, fallback to /opt install path
    app_dir = Path(__file__).resolve().parents[3]  # project root
    local_script = app_dir / "scripts" / "privileged" / "apply_router.sh"
    script_path = str(local_script) if local_script.exists() else "/opt/routergeist/scripts/privileged/apply_router.sh"
    try:
        # If we are root (e.g., inside the Docker container) run directly without sudo
        is_root = False
        try:
            is_root = os.geteuid() == 0  # type: ignore[attr-defined]
        except Exception:
            is_root = False
        cmd = ["/bin/bash", script_path, cfg_path] if is_root else [
            "sudo", "-n", "/bin/bash", script_path, cfg_path
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if not is_root and p.returncode != 0 and "password" in (p.stderr or "").lower():
            return "sudo requires a password. Configure passwordless sudo for apply_router.sh or run `sudo -v` before starting.\n" + (p.stderr or "")
        return (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"failed to invoke apply script: {exc}"


