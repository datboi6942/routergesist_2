from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict, List, Tuple

import psutil


class StatsService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        # per-nic history: list of (ts, rx_bytes, tx_bytes per second)
        self._history: Dict[str, Deque[Tuple[float, float, float]]] = {}
        self._window_seconds = 5 * 60

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
        prev = psutil.net_io_counters(pernic=True)
        prev_ts = time.time()
        while not self._stop.is_set():
            await asyncio.sleep(1)
            now_ts = time.time()
            now = psutil.net_io_counters(pernic=True)
            dt = max(1e-3, now_ts - prev_ts)
            async with self._lock:
                for nic, counters in now.items():
                    if nic not in prev:
                        continue
                    rx_rate = (counters.bytes_recv - prev[nic].bytes_recv) / dt
                    tx_rate = (counters.bytes_sent - prev[nic].bytes_sent) / dt
                    dq = self._history.setdefault(nic, deque(maxlen=self._window_seconds))
                    dq.append((now_ts, rx_rate, tx_rate))
                # Trim old points beyond window (in case maxlen not sufficient)
                cutoff = now_ts - self._window_seconds
                for dq in self._history.values():
                    while dq and dq[0][0] < cutoff:
                        dq.popleft()
            prev = now
            prev_ts = now_ts

    async def get_history(self) -> Dict[str, List[Tuple[float, float, float]]]:
        async with self._lock:
            return {k: list(v) for k, v in self._history.items()}


stats_service = StatsService()


