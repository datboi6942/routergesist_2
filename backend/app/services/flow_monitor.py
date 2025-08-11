from __future__ import annotations

import asyncio
import subprocess
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

from .threat_detector import threat_detector


class FlowMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        # sliding window of connections per remote IP
        self._events: Deque[Tuple[float, str, int]] = deque(maxlen=5000)
        self._lock = asyncio.Lock()
        self._window = 60.0
        self._rate_threshold = 80  # connections per IP per minute
        self._uncommon_ports = {23, 2323, 3389, 4444, 6667, 1337, 31337}

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
            await asyncio.sleep(2)

    async def _sample(self) -> None:
        now = time.time()
        new_conns: Dict[Tuple[str, int], int] = defaultdict(int)
        # Try ss for speed
        try:
            out = subprocess.check_output(["ss", "-ntu"], text=True)
            # skip header lines
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) < 5:
                    continue
                dst = parts[-1]
                # dst like 1.2.3.4:443 or [::ffff:1.2.3.4]:443
                if ']' in dst:
                    # strip brackets
                    try:
                        host_port = dst.split(']')[-1]
                        ip = dst.split(']')[0].split('[')[-1]
                        port = int(host_port.replace(':', ''))
                    except Exception:
                        continue
                else:
                    if ':' not in dst:
                        continue
                    ip, p = dst.rsplit(':', 1)
                    try:
                        port = int(p)
                    except Exception:
                        continue
                new_conns[(ip, port)] += 1
        except Exception:
            # Fallback to psutil snapshot
            if psutil:
                for c in psutil.net_connections(kind='inet'):
                    if not c.raddr:
                        continue
                    ip, port = c.raddr.ip, c.raddr.port
                    new_conns[(ip, port)] += 1

        async with self._lock:
            self._events.append((now, 'snapshot', sum(new_conns.values())))
        # Heuristics
        counts_per_ip: Dict[str, int] = defaultdict(int)
        suspicious_ports: Dict[str, int] = defaultdict(int)
        for (ip, port), n in new_conns.items():
            counts_per_ip[ip] += n
            if port in self._uncommon_ports:
                suspicious_ports[ip] += n

        for ip, count in counts_per_ip.items():
            if count >= self._rate_threshold:
                msg = f"Flow anomaly: high outbound connection rate to {ip} count={count} in ~{int(self._window)}s"
                await threat_detector.analyze(source="flow_monitor", message=msg)
        for ip, c in suspicious_ports.items():
            if c >= 5:
                msg = f"Flow anomaly: repeated connections to uncommon service from local host to {ip} occurrences={c}"
                await threat_detector.analyze(source="flow_monitor", message=msg)


flow_monitor = FlowMonitor()


