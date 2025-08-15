from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..security.auth import require_auth
from ..services.stats_service import stats_service
from ..services.dns_monitor import dns_monitor
import time
import subprocess
from typing import Dict, Any, List, Tuple, Optional
from ..services.router_config_store import router_config_store
from ..services.interface_manager import interface_manager
from ..services.activity_monitor import activity_monitor
from ..services.longterm_service import longterm_service


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
    """Return short-window averages and dynamic roles per NIC.

    Role selection precedence:
    1) Real-time roles from interface_manager ("WAN" or "AP" → label "LAN").
    2) Configured interfaces from router_config_store (LAN/WAN).
    3) Fallback to "other".
    """
    hist = await stats_service.get_history()
    # Gather runtime roles from interface_manager
    roles_map: Dict[str, str] = {}
    try:
        for info in await interface_manager.get_status():
            if info.role:
                roles_map[info.name] = "LAN" if info.role == "AP" else info.role
    except Exception:
        roles_map = {}

    # Config fallback
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
            role = roles_map.get(nic)
            if not role:
                role = "LAN" if nic == lan_if else ("WAN" if nic == wan_if else "other")
            pernic[nic] = {
                "rx_bps": sum(rx_vals) / max(1, len(rx_vals)),
                "tx_bps": sum(tx_vals) / max(1, len(tx_vals)),
                "role": role,
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


@router.get("/top-domains-by-client", dependencies=[Depends(require_auth)])
async def top_domains_by_client(limit: int = 10, window_seconds: int = 600) -> Dict[str, Any]:
    data = await dns_monitor.get_top_by_client(window_seconds=window_seconds, limit=limit)
    return {"by_client": data}


@router.get("/new-domains", dependencies=[Depends(require_auth)])
async def new_domains(window_seconds: int = 3600) -> Dict[str, Any]:
    items = await dns_monitor.get_new_domains(window_seconds=window_seconds)
    return {"items": items}


@router.get("/clients-by-domain", dependencies=[Depends(require_auth)])
async def clients_by_domain(limit: int = 10, window_seconds: int = 600) -> Dict[str, Any]:
    """Return top domains with counts of unique client queries within window.

    Response: { by_domain: { domain: [[client, count], ...], ... } }
    """
    by_client = await dns_monitor.get_recent_by_client(window_seconds=window_seconds)
    # invert to domain -> client -> count
    per_domain: Dict[str, Dict[str, int]] = {}
    for client, items in by_client.items():
        for domain, _ts in items:
            bucket = per_domain.setdefault(domain, {})
            bucket[client] = bucket.get(client, 0) + 1
    # pick top domains by total query count
    domain_totals: List[Tuple[str, int]] = [(dom, sum(m.values())) for dom, m in per_domain.items()]
    top = sorted(domain_totals, key=lambda kv: kv[1], reverse=True)[:limit]
    out: Dict[str, List[Tuple[str, int]]] = {}
    for dom, _tot in top:
        clients = per_domain.get(dom, {})
        out[dom] = sorted(clients.items(), key=lambda kv: kv[1], reverse=True)
    return {"by_domain": out}


@router.get("/clients-usage", dependencies=[Depends(require_auth)])
async def clients_usage() -> Dict[str, Any]:
    try:
        p = subprocess.run(["ss", "-ntu"], capture_output=True, text=True, check=False)
        lines = p.stdout.splitlines()
        per_src: Dict[str, int] = {}
        for ln in lines[1:]:
            parts = ln.split()
            if len(parts) < 5:
                continue
            local = parts[4]
            l_ip, _ = local.rsplit(":", 1)
            if l_ip.startswith("[") and "]" in l_ip:
                l_ip = l_ip.strip("[]")
            per_src[l_ip] = per_src.get(l_ip, 0) + 1
        items = sorted(per_src.items(), key=lambda kv: kv[1], reverse=True)
        return {"active_connections_by_client": items}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


@router.get("/activity", dependencies=[Depends(require_auth)])
async def activity() -> Dict[str, Any]:
    snap = await activity_monitor.get_snapshot()
    # return as list for stable iteration in UI
    items = sorted(snap.values(), key=lambda x: (0 if x.get("activity") == "streaming" else 1, -x.get("flows", 0)))
    return {"items": items}


@router.get("/longterm", dependencies=[Depends(require_auth)])
async def longterm(window_seconds: int = Query(24 * 3600, ge=60), nic: Optional[str] = None) -> Dict[str, Any]:
    """Return per-minute averages per NIC within the requested window.

    Response: { pernic: { nic: [[ts, rx_bps, tx_bps], ...], ... } }
    """
    data = await longterm_service.get_window(window_seconds=window_seconds, nic=nic)
    return {"pernic": data}

