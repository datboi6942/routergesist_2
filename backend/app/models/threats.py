from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ThreatEvent(BaseModel):
    id: str
    timestamp: datetime
    source: str
    message: str
    severity: str = Field(default="info")
    explanation: Optional[str] = None
    ip: Optional[str] = None
    action: Optional[str] = None  # e.g., "blocked_ip", "none"
    context: Optional[Dict[str, Any]] = None


class AnalyzeRequest(BaseModel):
    source: str
    message: str


class ThreatsResponse(BaseModel):
    events: List[ThreatEvent]


