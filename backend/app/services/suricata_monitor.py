from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import aiofiles

from .threat_detector import threat_detector


EVE_JSON = "/var/log/suricata/eve.json"
FAST_LOG = "/var/log/suricata/fast.log"


class SuricataMonitor:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

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
        if os.path.exists(EVE_JSON):
            await self._tail_eve(EVE_JSON)
        elif os.path.exists(FAST_LOG):
            await self._tail_fast(FAST_LOG)

    async def _tail_eve(self, path: str) -> None:
        try:
            async with aiofiles.open(path, "r") as f:
                await f.seek(0, os.SEEK_END)
                while not self._stop.is_set():
                    line = await f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("event_type") == "alert":
                        alert = obj.get("alert", {})
                        sig = alert.get("signature")
                        sev = alert.get("severity")  # 1 high, 2 medium, 3 low
                        src = obj.get("src_ip")
                        dst = obj.get("dest_ip")
                        msg = f"Suricata alert: {sig} (sev={sev}) src={src} dst={dst}"
                        await threat_detector.analyze(source="suricata", message=msg)
        except Exception:
            return

    async def _tail_fast(self, path: str) -> None:
        try:
            async with aiofiles.open(path, "r") as f:
                await f.seek(0, os.SEEK_END)
                while not self._stop.is_set():
                    line = await f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    # FAST format: timestamp [**] [gid:sid:rev] signature [Classification] [Priority] {proto} SRC:SPT -> DST:DPT
                    # We pass line as-is to the detector
                    await threat_detector.analyze(source="suricata", message=line.strip())
        except Exception:
            return


suricata_monitor = SuricataMonitor()


