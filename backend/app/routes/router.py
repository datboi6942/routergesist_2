from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..security.auth import require_auth
from ..services.router_config_store import router_config_store
from ..services.router_apply import apply_router_config
import subprocess
import os
import shutil


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
    """Return service status for key router components.

    Container-friendly: falls back to process and nftables checks when systemd
    is not available inside the environment.
    """
    status: Dict[str, str] = {}

    has_systemd = os.path.isdir("/run/systemd/system") and bool(shutil.which("systemctl"))

    for name in SERVICE_NAMES:
        try:
            if has_systemd:
                p = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, check=False)
                status[name] = p.stdout.strip() or p.stderr.strip()
                continue

            # Container mode fallbacks (no systemd):
            if name in {"dnsmasq", "routergeist-dnsmasq"}:
                p = subprocess.run(["pgrep", "-x", "dnsmasq"], capture_output=True, text=True)
                status[name] = "active" if p.returncode == 0 else "inactive"
            elif name in {"hostapd", "routergeist-hostapd"}:
                p = subprocess.run(["pgrep", "-x", "hostapd"], capture_output=True, text=True)
                status[name] = "active" if p.returncode == 0 else "inactive"
            elif name == "nftables":
                p = subprocess.run(["nft", "list", "tables"], capture_output=True, text=True)
                if p.returncode == 0 and ("routergeist_filter" in p.stdout or "routergeist_nat" in p.stdout):
                    status[name] = "active"
                else:
                    status[name] = "inactive"
            else:
                status[name] = "unknown"
        except Exception as exc:  # noqa: BLE001
            status[name] = f"error: {exc}"

    return {"status": status}


@router.post("/services/{name}/{action}", dependencies=[Depends(require_auth)])
async def services_ctl(name: str, action: str) -> Dict[str, Any]:
    if name not in SERVICE_NAMES:
        raise HTTPException(status_code=400, detail="Unknown service")
    if action not in {"start", "stop", "restart", "enable", "disable"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    has_systemd = os.path.isdir("/run/systemd/system") and bool(shutil.which("systemctl"))

    if has_systemd:
        p = subprocess.run(["sudo", "systemctl", action, name], capture_output=True, text=True, check=False)
        return {"ok": p.returncode == 0, "out": (p.stdout or "") + (p.stderr or "")}

    # Container mode control: reuse apply_router_config for (re)starts
    try:
        if action in {"start", "restart"}:
            out = apply_router_config()
            return {"ok": True, "out": out}
        if action == "stop":
            if name in {"dnsmasq", "routergeist-dnsmasq"}:
                subprocess.run(["pkill", "-x", "dnsmasq"], capture_output=True)
                return {"ok": True, "out": "dnsmasq stopped"}
            if name in {"hostapd", "routergeist-hostapd"}:
                subprocess.run(["pkill", "-x", "hostapd"], capture_output=True)
                return {"ok": True, "out": "hostapd stopped"}
            if name == "nftables":
                # Best-effort cleanup of routergeist tables
                subprocess.run(["nft", "delete", "table", "inet", "routergeist_filter"], capture_output=True)
                subprocess.run(["nft", "delete", "table", "ip", "routergeist_nat"], capture_output=True)
                return {"ok": True, "out": "nftables rules removed"}
            return {"ok": False, "out": "stop not supported for this service in container mode"}
        # enable/disable not applicable without systemd
        return {"ok": False, "out": "enable/disable not supported in container mode"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


