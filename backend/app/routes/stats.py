from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security.auth import require_auth
from ..services.stats_service import stats_service
from ..services.dns_monitor import dns_monitor


router = APIRouter()


@router.get("/traffic", dependencies=[Depends(require_auth)])
async def traffic() -> dict:
    return {"pernic": await stats_service.get_history()}


@router.get("/domains", dependencies=[Depends(require_auth)])
async def domains(limit: int = 200) -> dict:
    return {"recent": await dns_monitor.get_recent(limit=limit)}


