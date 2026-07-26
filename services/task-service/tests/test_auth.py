import asyncio
import uuid

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app import auth
from app.config import settings


def _make_token(secret: str = settings.jwt_secret_key, **overrides) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "performer",
        "type": "access",
        "iss": "user-service",
        **overrides,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_accepts_valid_token() -> None:
    user_id = uuid.uuid4()
    token = _make_token(sub=str(user_id), role="admin")

    current_user = asyncio.run(auth.get_current_user(credentials=_credentials(token)))

    assert current_user.id == user_id
    assert current_user.role == "admin"


def test_get_current_user_rejects_wrong_secret() -> None:
    token = _make_token(secret="not-the-shared-secret")
    with pytest.raises(Exception):
        asyncio.run(auth.get_current_user(credentials=_credentials(token)))


def test_get_current_user_rejects_refresh_token() -> None:
    token = _make_token(type="refresh")
    with pytest.raises(Exception):
        asyncio.run(auth.get_current_user(credentials=_credentials(token)))


def test_require_admin_rejects_non_admin() -> None:
    current_user = auth.CurrentUser(id=uuid.uuid4(), role="performer")
    with pytest.raises(Exception):
        asyncio.run(auth.require_admin(current_user=current_user))
