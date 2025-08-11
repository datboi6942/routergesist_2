from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..security.auth import require_auth
from ..services.router_config_store import router_config_store
from ..services.router_apply import apply_router_config
import subprocess


router = APIRouter()


class UpdateRequest(BaseModel):
    path: List[str]
    value: Any


class PortForward(BaseModel):
    proto: str
    in_port: int
    dest_ip: str
    dest_port: int


@router.get("/config", dependencies=[Depends(require_auth)])
async def get_config() -> Dict[str, Any]:
    return router_config_store.load()


@router.post("/config", dependencies=[Depends(require_auth)])
async def update_config(req: UpdateRequest) -> Dict[str, Any]:
    if not req.path:
        raise HTTPException(status_code=400, detail="path is required")
    return router_config_store.update(req.path, req.value)


@router.post("/forward", dependencies=[Depends(require_auth)])
async def add_forward(req: PortForward) -> Dict[str, Any]:
    return router_config_store.add_forward(req.proto, req.in_port, req.dest_ip, req.dest_port)


@router.delete("/forward/{index}", dependencies=[Depends(require_auth)])
async def remove_forward(index: int) -> Dict[str, Any]:
    return router_config_store.remove_forward(index)


@router.post("/apply", dependencies=[Depends(require_auth)])
async def apply() -> Dict[str, Any]:
    out = apply_router_config()
    return {"ok": True, "output": out}


SERVICE_NAMES = {
    "routergeist-dnsmasq",
    "routergeist-hostapd",
    "dnsmasq",
    "hostapd",
    "nftables",
}


@router.get("/services", dependencies=[Depends(require_auth)])
async def services_status() -> Dict[str, Any]:
    status = {}
    for name in SERVICE_NAMES:
        try:
            p = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, check=False)
            status[name] = p.stdout.strip() or p.stderr.strip()
        except Exception as exc:  # noqa: BLE001
            status[name] = f"error: {exc}"
    return {"status": status}


@router.post("/services/{name}/{action}", dependencies=[Depends(require_auth)])
async def services_ctl(name: str, action: str) -> Dict[str, Any]:
    if name not in SERVICE_NAMES:
        raise HTTPException(status_code=400, detail="Unknown service")
    if action not in {"start", "stop", "restart", "enable", "disable"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    p = subprocess.run(["sudo", "systemctl", action, name], capture_output=True, text=True, check=False)
    return {"ok": p.returncode == 0, "out": (p.stdout or "") + (p.stderr or "")}


