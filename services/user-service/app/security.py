import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_KEYS_DIR = Path(__file__).resolve().parent / "keys"
_PRIVATE_KEY_PATH = _KEYS_DIR / "private_key.pem"


def _load_or_create_private_key() -> rsa.RSAPrivateKey:
    _KEYS_DIR.mkdir(parents=True, exist_ok=True)
    if _PRIVATE_KEY_PATH.exists():
        return serialization.load_pem_private_key(_PRIVATE_KEY_PATH.read_bytes(), password=None)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _PRIVATE_KEY_PATH.write_bytes(pem)
    return key


PRIVATE_KEY = _load_or_create_private_key()
PUBLIC_KEY = PRIVATE_KEY.public_key()


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
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": settings.jwt_key_id})


def create_access_token(user_id: UUID, role: str) -> str:
    return _create_token(user_id, role, "access", timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: UUID, role: str) -> str:
    return _create_token(user_id, role, "refresh", timedelta(minutes=settings.refresh_token_expire_minutes))


def get_jwks() -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(PUBLIC_KEY))
    jwk.update({"use": "sig", "alg": "RS256", "kid": settings.jwt_key_id})
    return {"keys": [jwk]}
