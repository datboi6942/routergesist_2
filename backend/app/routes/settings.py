from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..security.auth import require_auth
from ..services.settings_store import settings_store
from ..services.threat_detector import threat_detector


router = APIRouter()


class OpenAISetRequest(BaseModel):
    api_key: str


@router.get("/openai")
async def get_openai_state(user: str = Depends(require_auth)) -> dict:
    return {"configured": settings_store.has_openai_key()}


@router.post("/openai")
async def set_openai_key(req: OpenAISetRequest, user: str = Depends(require_auth)) -> dict:
    key = req.api_key.strip()
    if not key or len(key.strip()) < 20 or not (key.startswith('sk-') or len(key) > 30):
        raise HTTPException(status_code=400, detail="Invalid API key")
    settings_store.set_openai_api_key(key)
    # Warm test: perform a minimal test call to validate key works
    try:
        await threat_detector.analyze(source="config", message="Test: key saved; validate connectivity")
        return {"ok": True}
    except Exception:
        return {"ok": False}


