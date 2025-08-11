from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from .config import settings
from .routes.interfaces import router as interfaces_router
from .routes.threats import router as threats_router
from .routes.nuke import router as nuke_router
from .routes.auth import router as auth_router
from .routes.settings import router as settings_router
from .routes.stats import router as stats_router
from .routes.router import router as router_cfg_router
from .services.interface_manager import interface_manager
from .services.stats_service import stats_service
from .services.dns_monitor import dns_monitor
from .services.suricata_monitor import suricata_monitor
from .services.flow_monitor import flow_monitor


app = FastAPI(title="Router Geist 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
async def on_startup() -> None:
    await interface_manager.start()
    await stats_service.start()
    await dns_monitor.start()
    await suricata_monitor.start()
    await flow_monitor.start()
    # Auto-apply router config at boot to bring up AP and NAT
    try:
        from .services.router_apply import apply_router_config
        apply_router_config()
    except Exception:
        pass


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await interface_manager.stop()
    await stats_service.stop()
    await dns_monitor.stop()
    await suricata_monitor.stop()
    await flow_monitor.stop()


app.include_router(interfaces_router, prefix="/api/interfaces", tags=["interfaces"])
app.include_router(threats_router, prefix="/api/threats", tags=["threats"])
app.include_router(nuke_router, prefix="/api/nuke", tags=["nuke"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
from .routes.security import router as security_router
app.include_router(security_router, prefix="/api/security", tags=["security"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
app.include_router(router_cfg_router, prefix="/api/router", tags=["router"])

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


