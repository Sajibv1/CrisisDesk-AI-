from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import error_response, success_response
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.admin import AdminUser
from app.schemas.auth import AdminLoginRequest, TokenResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=None)
def login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.username == payload.username).one_or_none()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        return error_response("Invalid credentials.", status_code=401)
    token = create_access_token(admin.username)
    return success_response("Login successful.", TokenResponse(access_token=token).model_dump())
