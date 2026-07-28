import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.security import create_access_token, create_refresh_token


@pytest.mark.asyncio
async def test_refresh_success() -> None:
    user_id = uuid.uuid4()
    refresh_token = create_refresh_token(user_id, "performer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["access_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_access_token() -> None:
    user_id = uuid.uuid4()
    access_token = create_access_token(user_id, "performer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401
