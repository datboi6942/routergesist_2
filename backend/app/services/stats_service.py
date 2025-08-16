from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict, List, Tuple
import json
import os

import psutil
from ..utils.paths import get_app_data_dir


class StatsService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        # per-nic history: list of (ts, rx_bytes, tx_bytes per second)
        self._history: Dict[str, Deque[Tuple[float, float, float]]] = {}
        # Keep 1 hour of history for long-horizon charts
        self._window_seconds = 60 * 60
        # Persist short-term window on disk for continuity across restarts
        self._path: str = os.path.join(get_app_data_dir(), "run", "shortterm.json")
        self._last_save_ts: float = 0.0

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        await self._load()
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
            # Sample at 2 Hz for smoother frontend graphs
            await asyncio.sleep(0.5)
            now_ts = time.time()
            now = psutil.net_io_counters(pernic=True)
            dt = max(1e-3, now_ts - prev_ts)
            async with self._lock:
                for nic, counters in now.items():
                    if nic not in prev:
                        continue
                    rx_rate = (counters.bytes_recv - prev[nic].bytes_recv) / dt
                    tx_rate = (counters.bytes_sent - prev[nic].bytes_sent) / dt
                    # Keep enough capacity for higher sample rate; trimming by time below
                    dq = self._history.setdefault(nic, deque(maxlen=int(self._window_seconds * 6)))
                    dq.append((now_ts, rx_rate, tx_rate))
                # Trim old points beyond window (in case maxlen not sufficient)
                cutoff = now_ts - self._window_seconds
                for dq in self._history.values():
                    while dq and dq[0][0] < cutoff:
                        dq.popleft()
                # Persist to disk at most every 5 seconds
                if (now_ts - self._last_save_ts) >= 5.0:
                    # Build a snapshot while holding the lock, then write outside
                    payload = {
                        "version": 1,
                        "pernic": {nic: list(dq) for nic, dq in self._history.items()},
                    }
                    # End of locked section
            if (now_ts - self._last_save_ts) >= 5.0:
                try:
                    await self._save_snapshot(payload)
                    self._last_save_ts = now_ts
                except Exception:
                    pass
            prev = now
            prev_ts = now_ts

    async def get_history(self) -> Dict[str, List[Tuple[float, float, float]]]:
        async with self._lock:
            return {k: list(v) for k, v in self._history.items()}

    async def _load(self) -> None:
        try:
            if not os.path.exists(self._path):
                return
            with open(self._path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            pernic = payload.get("pernic", {})
            now_ts = time.time()
            cutoff = now_ts - self._window_seconds
            async with self._lock:
                self._history = {
                    nic: deque([(float(ts), float(rx), float(tx)) for ts, rx, tx in lst if float(ts) >= cutoff],
                               maxlen=int(self._window_seconds * 6))
                    for nic, lst in pernic.items()
                }
        except Exception:
            # ignore load errors
            self._history = {}

    async def _save_snapshot(self, payload: Dict[str, object]) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, self._path)
        except Exception:
            # ignore save errors
            pass


stats_service = StatsService()


