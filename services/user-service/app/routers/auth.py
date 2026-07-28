import uuid

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import User, UserRole
from app.schemas import AccessTokenOut, AdminRegister, RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister
from app.security import create_access_token, create_refresh_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


async def _create_user(db: AsyncSession, email: str, password: str, role: UserRole) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    return await _create_user(db, data.email, data.password, UserRole.performer)


@router.post("/admin/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_admin(
    data: AdminRegister,
    db: AsyncSession = Depends(get_db),
    x_admin_secret: str | None = Header(default=None),
) -> User:
    if x_admin_secret != settings.admin_bootstrap_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin bootstrap secret")
    return await _create_user(db, data.email, data.password, UserRole.admin)


@router.post("/login", response_model=TokenPair)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
    )


@router.post("/refresh", response_model=AccessTokenOut)
async def refresh(data: RefreshRequest) -> AccessTokenOut:
    try:
        payload = jwt.decode(data.refresh_token, settings.jwt_secret_key, algorithms=["HS256"], issuer=settings.jwt_issuer)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return AccessTokenOut(access_token=create_access_token(uuid.UUID(payload["sub"]), payload["role"]))
