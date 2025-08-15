from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import settings
from ..utils.paths import get_app_data_dir
from ..services.router_apply import apply_router_config


WIRELESS_SYS_PATH = "/sys/class/net/{iface}/wireless"


@dataclass
class InterfaceInfo:
    name: str
    is_up: bool
    is_wireless: bool
    mac_address: Optional[str]
    ipv4_addresses: List[str]
    role: Optional[str]  # "AP", "WAN", or None


class InterfaceManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._interfaces: Dict[str, InterfaceInfo] = {}
        # Persist roles across scans to avoid repeated re-assignment
        self._roles: Dict[str, str] = {}
        # Track which iface we last applied AP stack for, to avoid flapping
        self._ap_applied_iface: Optional[str] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await asyncio.wait([self._task])

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._scan_and_assign()
            except Exception as exc:  # noqa: BLE001
                # Logged to stderr; keep running
                print(f"[interface_manager] error: {exc}")
            await asyncio.sleep(5)

    async def get_status(self) -> List[InterfaceInfo]:
        async with self._lock:
            return list(self._interfaces.values())

    async def assign_role(self, interface_name: str, role: str) -> None:
        async with self._lock:
            info = self._interfaces.get(interface_name)
            if not info:
                raise ValueError(f"Unknown interface: {interface_name}")
            if role not in ("AP", "WAN"):
                raise ValueError("Invalid role; must be 'AP' or 'WAN'")
            info.role = role
            self._roles[interface_name] = role
        # Apply role out-of-lock
        if role == "WAN":
            self._bring_up_wan(interface_name)
        elif role == "AP":
            self._bring_up_ap(interface_name)

    async def _scan_and_assign(self) -> None:
        interfaces = self._scan_interfaces()
        async with self._lock:
            self._interfaces = {i.name: i for i in interfaces}

        # Auto-assign logic
        wifi_ifaces = [i for i in interfaces if i.is_wireless]
        if not wifi_ifaces:
            return

        default_iface = self._get_default_route_iface()

        if len(wifi_ifaces) == 1:
            iface = wifi_ifaces[0]
            # If default route is on a different (non-wifi) iface, use wifi for AP
            if default_iface and default_iface != iface.name:
                if self._roles.get(iface.name) != "AP":
                    await self.assign_role(iface.name, "AP")
                return
            # Otherwise pick based on WAN credentials
            if iface.role is None:
                if self._wan_candidates_available():
                    await self.assign_role(iface.name, "WAN")
                else:
                    await self.assign_role(iface.name, "AP")
            return

        # Two or more wireless NICs
        # Prefer default-route iface for WAN if it is wireless; otherwise first wifi for WAN and the other for AP
        roles = {i.name: i.role for i in wifi_ifaces}
        names = [i.name for i in wifi_ifaces]

        chosen_wan = default_iface if default_iface in names else names[0]
        ap_candidates = [n for n in names if n != chosen_wan]
        if "WAN" not in roles.values():
            await self.assign_role(chosen_wan, "WAN")
        if "AP" not in roles.values() and ap_candidates:
            await self.assign_role(ap_candidates[0], "AP")

    def _scan_interfaces(self) -> List[InterfaceInfo]:
        result: List[InterfaceInfo] = []
        try:
            ip_output = subprocess.check_output(["ip", "-j", "addr"], text=True)
            data = json.loads(ip_output)
        except Exception:
            data = []

        for entry in data:
            name = entry.get("ifname")
            if not name or name == "lo":
                continue
            flags = entry.get("flags", [])
            is_up = "UP" in flags
            is_wireless = os.path.exists(WIRELESS_SYS_PATH.format(iface=name))
            mac = None
            if entry.get("address"):
                mac = entry["address"]
            ipv4s: List[str] = []
            for addr_info in entry.get("addr_info", []):
                if addr_info.get("family") == "inet":
                    ipv4s.append(addr_info.get("local"))
            info = InterfaceInfo(
                name=name,
                is_up=is_up,
                is_wireless=is_wireless,
                mac_address=mac,
                ipv4_addresses=ipv4s,
                role=self._roles.get(name),
            )
            result.append(info)
        return result

    def _wan_candidates_available(self) -> bool:
        if not settings.get_wan_credentials():
            return False
        # Optional: scan for SSIDs
        try:
            out = subprocess.check_output(["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"], text=True)
            ssids = {line.strip() for line in out.splitlines() if line.strip()}
            for ssid, _ in settings.get_wan_credentials():
                if ssid in ssids:
                    return True
        except Exception:
            pass
        return False

    def _bring_up_wan(self, iface: str) -> None:
        # Connect via NetworkManager if available
        for ssid, psk in settings.get_wan_credentials():
            try:
                cmd = ["nmcli", "device", "wifi", "connect", ssid, "ifname", iface]
                if psk:
                    cmd += ["password", psk]
                subprocess.run(cmd, check=False)
                print(f"[interface_manager] attempted WAN connect on {iface} to {ssid}")
                return
            except Exception as exc:  # noqa: BLE001
                print(f"[interface_manager] WAN connect error: {exc}")

    def _bring_up_ap(self, iface: str) -> None:
        # Delegate to systemd-managed apply script once to avoid flapping
        if self._ap_applied_iface == iface:
            return
        try:
            apply_router_config()
            self._ap_applied_iface = iface
            print(f"[interface_manager] ensured AP via apply_router_config on {iface}")
        except Exception as exc:  # noqa: BLE001
            print(f"[interface_manager] AP ensure error: {exc}")

    def _get_default_route_iface(self) -> Optional[str]:
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            for line in out.splitlines():
                parts = line.split()
                if "dev" in parts:
                    idx = parts.index("dev")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
        except Exception:
            pass
        return None


interface_manager = InterfaceManager()


