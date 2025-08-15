from __future__ import annotations

import asyncio
import ipaddress
import os
import time
from typing import Dict, List, Tuple

from .router_config_store import router_config_store
from .dns_monitor import dns_monitor


class ActivityMonitor:
    """Lightweight per-device activity classifier based on conntrack and recent DNS.

    - Samples /proc/net/nf_conntrack at ~2 Hz (no external deps)
    - Aggregates flows by client IP within LAN subnet
    - Heuristics to label streaming vs browsing vs download
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._snapshot: Dict[str, Dict[str, object]] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await asyncio.wait([self._task])

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._sample()
            except Exception:
                pass
            await asyncio.sleep(0.5)

    def _lan_network(self) -> ipaddress.IPv4Network | None:
        try:
            cfg = router_config_store.load()
            cidr = cfg.get("lan", {}).get("cidr")
            if cidr:
                return ipaddress.ip_network(cidr, strict=False)  # type: ignore[arg-type]
        except Exception:
            return None
        return None

    async def _sample(self) -> None:
        lan_net = self._lan_network()
        if lan_net is None:
            return

        now = time.time()
        per_client: Dict[str, Dict[str, int]] = {}

        # Parse /proc/net/nf_conntrack lines; fallback: none
        path = "/proc/net/nf_conntrack"
        lines: List[str] = []
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    # read limited lines to avoid heavy CPU
                    for _ in range(5000):
                        ln = f.readline()
                        if not ln:
                            break
                        lines.append(ln.strip())
        except Exception:
            lines = []

        for ln in lines:
            # Example tokens: "ipv4 2 tcp 6 431999 ESTABLISHED src=192.168.50.51 dst=172.217.0.14 sport=51324 dport=443 ..."
            if not ln:
                continue
            parts = ln.split()
            if len(parts) < 6:
                continue
            proto = parts[2]
            # pull first src= and dport=
            src_ip = None
            dport = None
            try:
                for t in parts:
                    if t.startswith("src=") and src_ip is None:
                        src_ip = t.split("=", 1)[1]
                    elif t.startswith("dport=") and dport is None:
                        dport = int(t.split("=", 1)[1])
                if src_ip is None:
                    continue
                if ipaddress.ip_address(src_ip) not in lan_net:  # type: ignore[arg-type]
                    continue
                bucket = per_client.setdefault(src_ip, {"flows": 0, "udp443": 0, "tcp443": 0})
                bucket["flows"] += 1
                if proto == "udp" and dport == 443:
                    bucket["udp443"] += 1
                if proto == "tcp" and dport == 443:
                    bucket["tcp443"] += 1
            except Exception:
                continue

        # Merge DNS context
        recent_by_client = await dns_monitor.get_top_by_client(window_seconds=600, limit=5)

        snapshot: Dict[str, Dict[str, object]] = {}
        for ip, counts in per_client.items():
            udp443 = counts.get("udp443", 0)
            tcp443 = counts.get("tcp443", 0)
            flows = counts.get("flows", 0)
            domains = [d for d, _ in recent_by_client.get(ip, [])]
            lower = ",".join(domains).lower()
            is_stream = udp443 >= 1 or any(x in lower for x in ("youtube", "netflix", "hulu", "twitch", "disney", "spotify", "primevideo", "vimeo"))
            activity = "streaming" if is_stream else ("downloading" if (tcp443 + udp443) >= 8 or flows >= 20 else ("active" if flows >= 2 else "idle"))
            snapshot[ip] = {
                "ip": ip,
                "activity": activity,
                "flows": flows,
                "udp443": udp443,
                "tcp443": tcp443,
                "top_domains": domains,
                "ts": now,
            }

        async with self._lock:
            self._snapshot = snapshot

    async def get_snapshot(self) -> Dict[str, Dict[str, object]]:
        async with self._lock:
            return dict(self._snapshot)


activity_monitor = ActivityMonitor()


