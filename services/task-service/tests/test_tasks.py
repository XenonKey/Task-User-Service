import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


def _admin_token() -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "type": "access",
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


@pytest.mark.asyncio
async def test_create_task_rejects_duplicate_title() -> None:
    title = f"Test task {uuid.uuid4()}"
    headers = {"Authorization": f"Bearer {_admin_token()}"}
    body = {"title": title, "description": "desc", "reward": "10.00"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/tasks", json=body, headers=headers)
        assert first.status_code == 201

        second = await client.post("/tasks", json=body, headers=headers)
        assert second.status_code == 409
