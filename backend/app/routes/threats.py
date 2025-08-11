from fastapi import APIRouter, Depends

from ..models.threats import AnalyzeRequest, ThreatsResponse
from ..security.auth import require_auth
from ..services.threat_detector import threat_detector


router = APIRouter()


@router.get("/", response_model=ThreatsResponse, dependencies=[Depends(require_auth)])
async def list_threats() -> ThreatsResponse:
    events = await threat_detector.list_events()
    return ThreatsResponse(events=events)


@router.post("/analyze", dependencies=[Depends(require_auth)])
async def analyze(req: AnalyzeRequest) -> dict:
    event = await threat_detector.analyze(source=req.source, message=req.message)
    return {"ok": True, "event": event}


