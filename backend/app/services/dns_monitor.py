from __future__ import annotations

import asyncio
import os
import re
from typing import Deque, Dict, List, Tuple
from collections import deque

from ..utils.paths import get_app_data_dir


RESOLVED_LOG = "/var/log/dnsmasq.log"  # common path if using dnsmasq logging
ALT_JOURNALCTL = ["journalctl", "-u", "systemd-resolved", "-o", "cat", "-f"]
DOMAIN_RE = re.compile(r"query\[[A-Z]+\]\s+([a-zA-Z0-9_.-]+)")


class DNSMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._visited: Deque[Tuple[float, str]] = deque(maxlen=2000)

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
                        async with self._lock:
                            self._visited.append((time.time(), domain))
        except Exception:
            return

    async def get_recent(self, limit: int = 200) -> List[Tuple[float, str]]:
        async with self._lock:
            return list(self._visited)[-limit:]


dns_monitor = DNSMonitor()


