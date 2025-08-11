from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..security.auth import require_auth
from ..services.firewall import block_ip
from ..services.blocklist_store import blocklist_store


router = APIRouter()


class BlockRequest(BaseModel):
    ip: str


@router.post("/block", dependencies=[Depends(require_auth)])
async def block(req: BlockRequest) -> dict:
    ok = block_ip(req.ip)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to block IP")
    blocklist_store.add(req.ip)
    return {"ok": True}


@router.get("/blocklist", dependencies=[Depends(require_auth)])
async def get_blocklist() -> dict:
    return {"ips": blocklist_store.list()}


