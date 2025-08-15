from __future__ import annotations

import asyncio
import os
import re
from typing import Deque, Dict, List, Tuple
from collections import deque

from ..utils.paths import get_app_data_dir


RESOLVED_LOG = "/var/log/dnsmasq.log"  # common path if using dnsmasq logging
ALT_JOURNALCTL = ["journalctl", "-u", "systemd-resolved", "-o", "cat", "-f"]
# Example: "query[A] example.com from 192.168.50.51"
DOMAIN_RE = re.compile(r"query\[[A-Z]+\]\s+([a-zA-Z0-9_.-]+)\s+from\s+([0-9a-fA-F:.]+)")


class DNSMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._visited: Deque[Tuple[float, str, str]] = deque(maxlen=5000)
        self._first_seen: Dict[str, float] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_best_effort())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await asyncio.wait([self._task])

    async def _run_best_effort(self) -> None:
        # Best-effort: tail dnsmasq log if present; otherwise do nothing
        if os.path.exists(RESOLVED_LOG):
            await self._tail_file(RESOLVED_LOG)
            return
        # Could add journalctl parsing here if resolved is used

    async def _tail_file(self, path: str) -> None:
        import aiofiles
        import time

        # Simple tail-f style follow
        try:
            async with aiofiles.open(path, "r") as f:
                await f.seek(0, os.SEEK_END)
                while not self._stop.is_set():
                    line = await f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    m = DOMAIN_RE.search(line)
                    if m:
                        domain = m.group(1).lower()
                        client = m.group(2)
                        now = time.time()
                        async with self._lock:
                            self._visited.append((now, domain, client))
                            if domain not in self._first_seen:
                                self._first_seen[domain] = now
        except Exception:
            return

    async def get_recent(self, limit: int = 200) -> List[Tuple[float, str]]:
        async with self._lock:
            return [(ts, dom) for ts, dom, _ in list(self._visited)[-limit:]]

    async def get_recent_by_client(self, window_seconds: int = 600) -> Dict[str, List[Tuple[str, float]]]:
        import time
        cutoff = time.time() - window_seconds
        out: Dict[str, List[Tuple[str, float]]] = {}
        async with self._lock:
            for ts, dom, client in self._visited:
                if ts < cutoff:
                    continue
                out.setdefault(client, []).append((dom, ts))
        return out

    async def get_top_by_client(self, window_seconds: int = 600, limit: int = 10) -> Dict[str, List[Tuple[str, int]]]:
        import time
        cutoff = time.time() - window_seconds
        counts: Dict[str, Dict[str, int]] = {}
        async with self._lock:
            for ts, dom, client in self._visited:
                if ts < cutoff:
                    continue
                bucket = counts.setdefault(client, {})
                bucket[dom] = bucket.get(dom, 0) + 1
        top: Dict[str, List[Tuple[str, int]]] = {}
        for client, m in counts.items():
            items = sorted(m.items(), key=lambda kv: kv[1], reverse=True)[:limit]
            top[client] = items
        return top

    async def get_new_domains(self, window_seconds: int = 3600) -> List[Tuple[float, str]]:
        import time
        cutoff = time.time() - window_seconds
        async with self._lock:
            items = [(ts, dom) for dom, ts in self._first_seen.items() if ts >= cutoff]
        return sorted(items, key=lambda x: x[0], reverse=True)


dns_monitor = DNSMonitor()


