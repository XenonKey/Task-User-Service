from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def _create_token(user_id: UUID, role: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_access_token(user_id: UUID, role: str) -> str:
    return _create_token(user_id, role, "access", timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: UUID, role: str) -> str:
    return _create_token(user_id, role, "refresh", timedelta(minutes=settings.refresh_token_expire_minutes))
