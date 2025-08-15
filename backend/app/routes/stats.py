from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security.auth import require_auth
from ..services.stats_service import stats_service
from ..services.dns_monitor import dns_monitor
import time
import subprocess
from typing import Dict, Any, List, Tuple
from ..services.router_config_store import router_config_store


router = APIRouter()


@router.get("/traffic", dependencies=[Depends(require_auth)])
async def traffic() -> dict:
    return {"pernic": await stats_service.get_history()}


@router.get("/domains", dependencies=[Depends(require_auth)])
async def domains(limit: int = 200) -> dict:
    return {"recent": await dns_monitor.get_recent(limit=limit)}


@router.get("/top-domains", dependencies=[Depends(require_auth)])
async def top_domains(limit: int = 10, window_seconds: int = 600) -> Dict[str, Any]:
    now = time.time()
    recent: List[Tuple[float, str]] = await dns_monitor.get_recent(limit=2000)
    counts: Dict[str, int] = {}
    for ts, domain in recent:
        if now - ts <= window_seconds:
            counts[domain] = counts.get(domain, 0) + 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return {"items": items}


@router.get("/summary", dependencies=[Depends(require_auth)])
async def summary(window_seconds: int = 120) -> Dict[str, Any]:
    # Compute average rx/tx over window for each NIC; also mark LAN/WAN from config
    hist = await stats_service.get_history()
    cfg = router_config_store.load()
    lan_if = cfg.get("lan", {}).get("interface")
    wan_if = cfg.get("wan", {}).get("interface")
    now = time.time()
    pernic: Dict[str, Dict[str, float]] = {}
    for nic, points in hist.items():
        rx_vals: List[float] = []
        tx_vals: List[float] = []
        for ts, rx, tx in points:
            if now - ts <= window_seconds:
                rx_vals.append(rx)
                tx_vals.append(tx)
        if rx_vals or tx_vals:
            pernic[nic] = {
                "rx_bps": sum(rx_vals) / max(1, len(rx_vals)),
                "tx_bps": sum(tx_vals) / max(1, len(tx_vals)),
                "role": "LAN" if nic == lan_if else ("WAN" if nic == wan_if else "other"),
            }
    return {"pernic": pernic}


@router.get("/connections", dependencies=[Depends(require_auth)])
async def connections() -> Dict[str, Any]:
    # Best-effort: use ss to list TCP/UDP connections and aggregate by local src IP
    try:
        p = subprocess.run(["ss", "-ntu"], capture_output=True, text=True, check=False)
        lines = p.stdout.splitlines()
        per_src: Dict[str, int] = {}
        per_dport: Dict[str, int] = {}
        for ln in lines[1:]:
            parts = ln.split()
            if len(parts) < 5:
                continue
            # format: Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port
            local = parts[4]
            peer = parts[5] if len(parts) > 5 else ""
            # Extract IP and port
            l_ip, l_port = local.rsplit(":", 1)
            if l_ip.startswith("[") and "]" in l_ip:
                l_ip = l_ip.strip("[]")
            per_src[l_ip] = per_src.get(l_ip, 0) + 1
            if ":" in peer:
                _, d_port = peer.rsplit(":", 1)
                per_dport[d_port] = per_dport.get(d_port, 0) + 1
        top_src = sorted(per_src.items(), key=lambda kv: kv[1], reverse=True)[:20]
        top_dports = sorted(per_dport.items(), key=lambda kv: kv[1], reverse=True)[:20]
        return {"top_clients": top_src, "top_dest_ports": top_dports}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


