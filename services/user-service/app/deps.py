import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.models import UserRole

bearer_scheme = HTTPBearer()


@dataclass
class CurrentUser:
    id: uuid.UUID
    role: str


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> CurrentUser:
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=["HS256"], issuer=settings.jwt_issuer)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return CurrentUser(id=uuid.UUID(payload["sub"]), role=payload["role"])


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
