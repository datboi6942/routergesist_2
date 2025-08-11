from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..models.interfaces import InterfacesResponse, InterfaceStatus, AssignRoleRequest
from ..security.auth import require_auth
from ..services.interface_manager import interface_manager, InterfaceInfo


router = APIRouter()


@router.get("/", response_model=InterfacesResponse, dependencies=[Depends(require_auth)])
async def list_interfaces() -> InterfacesResponse:
    infos: List[InterfaceInfo] = await interface_manager.get_status()
    return InterfacesResponse(
        interfaces=[
            InterfaceStatus(
                name=i.name,
                is_up=i.is_up,
                is_wireless=i.is_wireless,
                mac_address=i.mac_address,
                ipv4_addresses=i.ipv4_addresses,
                role=i.role,
            )
            for i in infos
        ]
    )


@router.post("/assign", dependencies=[Depends(require_auth)])
async def assign_role(req: AssignRoleRequest) -> dict:
    try:
        await interface_manager.assign_role(req.interface_name, req.role)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


