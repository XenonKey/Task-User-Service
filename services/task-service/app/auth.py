import asyncio
import json
import logging
import uuid
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm

from .config import settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer()

_public_key = None


async def load_public_key() -> None:
    """Fetch and cache user-service's RSA public key via JWKS at startup.

    After this, JWT verification is fully local -- no per-request network call
    to user-service.
    """
    global _public_key
    async with httpx.AsyncClient() as client:
        for attempt in range(1, settings.jwks_fetch_retries + 1):
            try:
                response = await client.get(settings.user_service_jwks_url, timeout=5.0)
                response.raise_for_status()
                jwk = response.json()["keys"][0]
                _public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))
                logger.info("Loaded JWT public key from %s", settings.user_service_jwks_url)
                return
            except (httpx.HTTPError, KeyError, IndexError) as exc:
                logger.warning(
                    "Failed to fetch JWKS (attempt %s/%s): %s",
                    attempt,
                    settings.jwks_fetch_retries,
                    exc,
                )
                await asyncio.sleep(settings.jwks_fetch_retry_delay_seconds)
    raise RuntimeError(f"Could not fetch JWKS from {settings.user_service_jwks_url}")


@dataclass
class CurrentUser:
    id: uuid.UUID
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    if _public_key is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth is not ready yet")
    try:
        payload = jwt.decode(
            credentials.credentials, _public_key, algorithms=["RS256"], issuer=settings.jwt_issuer
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return CurrentUser(id=uuid.UUID(payload["sub"]), role=payload["role"])


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
