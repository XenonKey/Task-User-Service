import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email() -> None:
    email = f"test-{uuid.uuid4()}@example.com"
    body = {"email": email, "password": "supersecret123"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/auth/register", json=body)
        assert first.status_code == 201

        second = await client.post("/auth/register", json=body)
        assert second.status_code == 409
