"""Authentication endpoints and dependencies."""

import os
import uuid
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

from config import settings
from core.auth import create_access_token, verify_access_token
from core.db import get_db
from core.redis_client import get_redis
from models.envelope import build_envelope
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]

def _extract_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT from HTTP-only cookie (primary) or Authorization header (fallback)."""
    token = request.cookies.get("dss_access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Dependency injecting the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "false").lower() == "true":
        # Desktop bypass uses a persisted local owner so FK-backed settings writes succeed.
        result = await db.execute(select(User).where(User.id == "local_desktop"))
        user = result.scalars().first()
        if user is None:
            user = User(
                id="local_desktop",
                email="local@drugsynth.local",
                full_name="Local User",
                display_name="Local User",
                hashed_password="desktop-bypass",
                role="admin",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    token = _extract_token_from_request(request)
    if not token:
        raise credentials_exception

    payload = verify_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

REFRESH_TOKEN_TTL = settings.refresh_token_expire_days * 86400  # 7 days in seconds
_SECURE_COOKIE = lambda: os.environ.get("DSS_SECURE_COOKIES", "true").lower() == "true"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set both access and refresh token HTTP-only cookies."""
    response.set_cookie(
        key="dss_access_token",
        value=access_token,
        httponly=True,
        secure=_SECURE_COOKIE(),
        samesite="strict",
        max_age=settings.jwt_expire_minutes * 60,
        path="/api",
    )
    response.set_cookie(
        key="dss_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE(),
        samesite="strict",
        max_age=REFRESH_TOKEN_TTL,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear both auth cookies on logout."""
    response.delete_cookie(key="dss_access_token", path="/api", httponly=True, secure=_SECURE_COOKIE(), samesite="strict")
    response.delete_cookie(key="dss_refresh_token", path="/api/v1/auth", httponly=True, secure=_SECURE_COOKIE(), samesite="strict")


@router.post("/register", response_model=UserOut)
async def register(user: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = pwd_context.hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password, full_name=user.full_name)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    from core.audit import log_audit
    await log_audit(db, user_id=db_user.id, action="register", resource_type="user", resource_id=db_user.id, ip_address=request.client.host if request.client else None)
    await db.commit()
    return db_user

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    if not os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "false").lower() == "true":
        # Pass-through in desktop — still set cookie for consistent flow
        response = JSONResponse(content={"user": {"id": "local_desktop", "email": "local@drugsynth.local", "full_name": "Local User"}})
        response.set_cookie(
            key="dss_access_token",
            value="local_token",
            httponly=True,
            secure=_SECURE_COOKIE(),
            samesite="strict",
            max_age=settings.jwt_expire_minutes * 60,
            path="/api",
        )
        return response

    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.id})
    # §55.1: Opaque refresh token stored in Redis with 7-day TTL
    refresh_tok = str(uuid.uuid4())
    redis = await get_redis()
    await redis.setex(f"refresh:{refresh_tok}", REFRESH_TOKEN_TTL, str(user.id))

    from core.audit import log_audit
    await log_audit(db, user_id=str(user.id), action="login", resource_type="session", resource_id=refresh_tok[:8], ip_address=request.client.host if request.client else None)
    await db.commit()

    response = JSONResponse(content={
        "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name}
    })
    _set_auth_cookies(response, access_token, refresh_tok)
    return response

@router.get("/me")
async def read_users_me(request: Request, current_user: User = Depends(get_current_user)):
    return build_envelope(request, {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": getattr(current_user, "role", "user"),
    })


class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """§55.1: Rotate refresh token stored in Redis. Issue new access + refresh tokens."""
    old_refresh = request.cookies.get("dss_refresh_token")
    if not old_refresh:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    redis = await get_redis()
    user_id = await redis.get(f"refresh:{old_refresh}")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Rotate: invalidate old token
    await redis.delete(f"refresh:{old_refresh}")

    # Issue new tokens
    access_token = create_access_token(data={"sub": user_id})
    new_refresh = str(uuid.uuid4())
    await redis.setex(f"refresh:{new_refresh}", REFRESH_TOKEN_TTL, user_id)

    # Return user info
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    user_data = {"id": user_id, "email": getattr(user, "email", ""), "full_name": getattr(user, "full_name", None)}

    response = JSONResponse(content={"user": user_data})
    _set_auth_cookies(response, access_token, new_refresh)
    return response


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """§22: Logout — clear cookies and invalidate refresh token in Redis."""
    old_refresh = request.cookies.get("dss_refresh_token")
    if old_refresh:
        try:
            redis = await get_redis()
            await redis.delete(f"refresh:{old_refresh}")
        except Exception:
            pass  # Best-effort Redis cleanup

    try:
        from core.audit import log_audit
        token = _extract_token_from_request(request)
        uid = "system"
        if token:
            payload = verify_access_token(token)
            if payload:
                uid = payload.get("sub", "system")
        await log_audit(db, user_id=uid, action="logout", resource_type="session", resource_id="", ip_address=request.client.host if request.client else None)
        await db.commit()
    except Exception:
        pass

    response = JSONResponse(content={"detail": "Logged out successfully"})
    _clear_auth_cookies(response)
    return response


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """§22: Change the authenticated user's password."""
    if not os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "false").lower() == "true":
        raise HTTPException(status_code=400, detail="Auth is not enabled in workbench mode")

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not pwd_context.verify(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = pwd_context.hash(req.new_password)
    await db.commit()
    return build_envelope(request, {"detail": "Password changed successfully"})
