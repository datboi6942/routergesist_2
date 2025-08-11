from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..security.auth import create_session, clear_session, require_auth
from ..services.credential_store import credential_store


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("/state")
async def state(user: str = Depends(require_auth)) -> dict:
    return {"authenticated": True, "user": user}


@router.post("/login")
async def login(req: LoginRequest, response: Response) -> dict:
    admin = credential_store.get_admin()
    if not admin:
        raise HTTPException(status_code=503, detail="Admin not initialized. Set credentials via config file.")
    if req.username != admin.username or not credential_store.verify(req.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    create_session(response, admin.username)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_session(response)
    return {"ok": True}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: str = Depends(require_auth)) -> dict:
    admin = credential_store.get_admin()
    if not admin:
        raise HTTPException(status_code=503, detail="Admin not initialized")
    if not credential_store.verify(req.current_password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid current password")
    if len(req.new_password) < 10:
        raise HTTPException(status_code=400, detail="New password too short")
    credential_store.update_password(req.new_password)
    return {"ok": True}


class BootstrapRequest(BaseModel):
    username: str
    password: str


@router.post("/bootstrap")
async def bootstrap(req: BootstrapRequest) -> dict:
    # Allow bootstrap only if no admin exists yet
    if credential_store.has_admin():
        raise HTTPException(status_code=400, detail="Admin already initialized")
    if len(req.password) < 10:
        raise HTTPException(status_code=400, detail="Password too short")
    credential_store.set_admin(req.username, req.password)
    return {"ok": True}


@router.get("/bootstrap-allowed")
async def bootstrap_allowed() -> dict:
    return {"allowed": not credential_store.has_admin()}


