from fastapi import APIRouter, Depends, HTTPException

from ..models.nuke import NukeRequest, NukeResponse
from ..security.auth import require_auth
from ..services.nuke_service import nuke as nuke_impl


router = APIRouter()


@router.post("/", response_model=NukeResponse, dependencies=[Depends(require_auth)])
async def nuke(req: NukeRequest) -> NukeResponse:
    if req.confirmation.strip().upper() != "NUKE":
        raise HTTPException(status_code=400, detail="Confirmation text mismatch")
    msg = nuke_impl(full_device=req.full_device)
    return NukeResponse(started=True, message=msg)


