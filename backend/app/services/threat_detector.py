from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List

from ..config import settings
from .settings_store import settings_store
from ..models.threats import ThreatEvent
from .firewall import block_ip


class ThreatDetector:
    def __init__(self) -> None:
        self._events: List[ThreatEvent] = []
        self._lock = asyncio.Lock()

    async def analyze(self, source: str, message: str) -> ThreatEvent:
        severity = "info"
        explanation = None
        # Prefer stored key; fall back to env
        api_key = settings_store.get_openai_api_key() or settings.openai_api_key
        if api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, base_url=settings.openai_api_base)
                prompt = (
                    "You are a network security assistant on a router. "
                    "Classify the following event by severity (low, medium, high, critical), explain briefly why it's suspicious, and extract any suspicious IP if present as JSON fields: {severity, explanation, ip}.\n\n"
                    f"Event: {message}\n"
                )
                resp = client.chat.completions.create(
                    model="gpt-5",
                    messages=[{"role": "system", "content": "You are a concise security analyst."}, {"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                text = resp.choices[0].message.content or ""
                explanation = text.strip()[:1500]
                lowered = explanation.lower()
                if any(k in lowered for k in ["critical", "severe", "urgent"]):
                    severity = "critical"
                elif "high" in lowered:
                    severity = "high"
                elif "medium" in lowered:
                    severity = "medium"
                else:
                    severity = "low"
                # Extract ip if formatted JSON appears
                try:
                    import json as _json
                    jstart = text.find('{')
                    jend = text.rfind('}')
                    if jstart != -1 and jend != -1 and jend > jstart:
                        j = _json.loads(text[jstart:jend+1])
                        if isinstance(j, dict):
                            if j.get('severity'):
                                severity = str(j['severity']).lower()
                            if j.get('explanation'):
                                explanation = str(j['explanation'])[:1500]
                            if j.get('ip'):
                                ip_in_msg = str(j['ip'])
                except Exception:
                    pass
            except Exception:
                explanation = None
                severity = "info"

        ip_in_msg = None
        try:
            import re
            m = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", message)
            if m:
                ip_in_msg = m.group(0)
        except Exception:
            pass

        event = ThreatEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            source=source,
            message=message,
            severity=severity,
            explanation=explanation,
            ip=ip_in_msg,
            action=None,
            context={"analyzer": "llm" if api_key else "local"}
        )
        async with self._lock:
            self._events.append(event)
            self._events = self._events[-500:]
        # Auto-block heuristic: if a source string includes an IP and severity high/critical
        try:
            if event.ip and severity in ("high", "critical"):
                if block_ip(event.ip):
                    event.action = "blocked_ip"
        except Exception:
            event.action = event.action or None
        return event

    async def list_events(self) -> List[ThreatEvent]:
        async with self._lock:
            return list(self._events)


threat_detector = ThreatDetector()


