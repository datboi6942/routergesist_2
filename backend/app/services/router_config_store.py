from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..utils.paths import get_app_data_dir


DEFAULT_CONFIG: Dict[str, Any] = {
    "admin": {
        "port": 8080,
    },
    "lan": {
        "interface": "eth0",
        "cidr": "192.168.50.1/24",
        "dhcp_start": "192.168.50.50",
        "dhcp_end": "192.168.50.200",
        "dns": ["1.1.1.1", "9.9.9.9"],
    },
    "wan": {
        "mode": "dhcp",  # dhcp | static | pppoe
        "interface": "wlp1s0",
        "static": {"address": "", "gateway": "", "dns": []},
        "pppoe": {"username": "", "password": ""},
    },
    "wifi": {
        # interface is auto-selected on first apply if unset or conflicts with WAN
        "interface": "",
        "ssid": "RouterGeist",
        "psk": "ChangeMe1234",
        "country": "US",
        "channel": 1,
        "guest_enabled": False,
        "guest_ssid": "RouterGeist-Guest",
        "guest_psk": "ChangeMe1234",
    },
    "forwards": [],  # list of {proto: tcp/udp, in_port, dest_ip, dest_port}
    "dhcp_reservations": [],  # list of {mac, ip, hostname}
    "dns_overrides": [],  # list of {host, ip}
}


class RouterConfigStore:
    def __init__(self) -> None:
        self._dir = get_app_data_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._file = os.path.join(self._dir, "router_config.json")

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self._file):
            return DEFAULT_CONFIG.copy()
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save(self, cfg: Dict[str, Any]) -> None:
        tmp = self._file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, self._file)
        os.chmod(self._file, 0o600)

    def update(self, path: List[str], value: Any) -> Dict[str, Any]:
        cfg = self.load()
        ref = cfg
        for key in path[:-1]:
            if key not in ref or not isinstance(ref[key], dict):
                ref[key] = {}
            ref = ref[key]
        ref[path[-1]] = value
        self.save(cfg)
        return cfg

    def add_forward(self, proto: str, in_port: int, dest_ip: str, dest_port: int) -> Dict[str, Any]:
        cfg = self.load()
        forwards: List[Dict[str, Any]] = cfg.get("forwards", [])
        forwards.append({"proto": proto, "in_port": in_port, "dest_ip": dest_ip, "dest_port": dest_port})
        cfg["forwards"] = forwards
        self.save(cfg)
        return cfg

    def remove_forward(self, index: int) -> Dict[str, Any]:
        cfg = self.load()
        fwd = cfg.get("forwards", [])
        if 0 <= index < len(fwd):
            del fwd[index]
        cfg["forwards"] = fwd
        self.save(cfg)
        return cfg


router_config_store = RouterConfigStore()


