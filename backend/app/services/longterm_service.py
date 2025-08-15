from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from .stats_service import stats_service
from ..utils.paths import get_app_data_dir


class LongTermService:
    """Persist per-minute per-NIC rx/tx averages for up to 7 days.

    Stores data in a small JSON file under the app data directory so it survives restarts.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        # per-nic minute samples: (ts_seconds, rx_bps, tx_bps)
        self._mins: Dict[str, Deque[Tuple[float, float, float]]] = {}
        self._max_minutes: int = 7 * 24 * 60  # 7d
        # Persist under app data directory "run" subfolder to align with deployment layout
        self._path: str = os.path.join(get_app_data_dir(), "run", "longterm.json")

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
        await self._save()

    async def _run(self) -> None:
        # Align roughly to minute boundaries, but don't be strict
        while not self._stop.is_set():
            try:
                await self._sample_minute()
                # sleep the remainder of the minute
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                # best-effort: don't crash background task
                await asyncio.sleep(5)

    async def _sample_minute(self) -> None:
        now_ts = time.time()
        # compute per-minute peaks over last 60 seconds using stats_service history
        hist = await stats_service.get_history()
        cutoff = now_ts - 60.0
        pernic_peaks: Dict[str, Tuple[float, float]] = {}
        for nic, points in hist.items():
            recent = [p for p in points if p[0] >= cutoff]
            if not recent:
                continue
            # Use peak within the minute to better capture bursty traffic
            rx = max(p[1] for p in recent)
            tx = max(p[2] for p in recent)
            pernic_peaks[nic] = (rx, tx)
        if not pernic_peaks:
            return
        async with self._lock:
            for nic, (rx, tx) in pernic_peaks.items():
                dq = self._mins.setdefault(nic, deque(maxlen=self._max_minutes))
                dq.append((now_ts, rx, tx))
            # trim any over-long deques (maxlen should handle it)
            for dq in self._mins.values():
                while len(dq) > self._max_minutes:
                    dq.popleft()
        await self._save()

    async def get_window(self, window_seconds: int, nic: Optional[str] = None) -> Dict[str, List[Tuple[float, float, float]]]:
        now = time.time()
        start = now - max(0, window_seconds)
        async with self._lock:
            if nic is not None:
                data = list(self._mins.get(nic, []))
                return {nic: [p for p in data if p[0] >= start]}
            result: Dict[str, List[Tuple[float, float, float]]] = {}
            for name, dq in self._mins.items():
                result[name] = [p for p in dq if p[0] >= start]
            return result

    async def _load(self) -> None:
        try:
            if not os.path.exists(self._path):
                return
            with open(self._path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            mins = payload.get("pernic", {})
            async with self._lock:
                self._mins = {
                    nic: deque([(float(ts), float(rx), float(tx)) for ts, rx, tx in lst], maxlen=self._max_minutes)
                    for nic, lst in mins.items()
                }
        except Exception:
            # ignore load errors
            self._mins = {}

    async def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            async with self._lock:
                payload = {
                    "version": 1,
                    "pernic": {nic: list(dq) for nic, dq in self._mins.items()},
                }
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, self._path)
        except Exception:
            # ignore save errors
            pass


longterm_service = LongTermService()


