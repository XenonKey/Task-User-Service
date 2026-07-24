import asyncio
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth


def _make_token(private_key: rsa.RSAPrivateKey, **overrides) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "performer",
        "type": "access",
        "iss": "user-service",
        **overrides,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture(autouse=True)
def restore_public_key():
    original = auth._public_key
    yield
    auth._public_key = original


def test_get_current_user_rejects_when_key_not_loaded() -> None:
    auth._public_key = None
    with pytest.raises(Exception):
        asyncio.run(auth.get_current_user(credentials=None))  # type: ignore[arg-type]


def test_require_admin_rejects_non_admin() -> None:
    current_user = auth.CurrentUser(id=uuid.uuid4(), role="performer")
    with pytest.raises(Exception):
        asyncio.run(auth.require_admin(current_user=current_user))
