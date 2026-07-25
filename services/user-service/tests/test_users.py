import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.main import app
from app.models import User, UserRole


class FakeSession:
    def __init__(self, user: User | None) -> None:
        self._user = user

    async def get(self, model: type[User], id_: uuid.UUID) -> User | None:
        if self._user is not None and id_ == self._user.id:
            return self._user
        return None


def make_user(role: UserRole = UserRole.performer, balance: Decimal = Decimal("10.00")) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        role=role,
        balance=balance,
        created_at=datetime.now(timezone.utc),
    )


def override_dependencies(current_user: CurrentUser, db_user: User | None) -> None:
    async def fake_get_current_user() -> CurrentUser:
        return current_user

    async def fake_get_db():
        yield FakeSession(db_user)

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_db] = fake_get_db


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_read_me_success() -> None:
    user = make_user()
    override_dependencies(CurrentUser(id=user.id, role=user.role.value), user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["role"] == user.role.value


@pytest.mark.asyncio
async def test_read_me_not_found() -> None:
    override_dependencies(CurrentUser(id=uuid.uuid4(), role=UserRole.performer.value), None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/users/me")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_read_balance_own() -> None:
    user = make_user(balance=Decimal("42.50"))
    override_dependencies(CurrentUser(id=user.id, role=user.role.value), user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/users/{user.id}/balance")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.id)
    assert Decimal(body["balance"]) == Decimal("42.50")


@pytest.mark.asyncio
async def test_read_balance_forbidden_for_other_performer() -> None:
    target_user = make_user()
    override_dependencies(CurrentUser(id=uuid.uuid4(), role=UserRole.performer.value), target_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/users/{target_user.id}/balance")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_read_balance_admin_can_read_others() -> None:
    target_user = make_user(balance=Decimal("100.00"))
    override_dependencies(CurrentUser(id=uuid.uuid4(), role=UserRole.admin.value), target_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/users/{target_user.id}/balance")

    assert response.status_code == 200
    assert Decimal(response.json()["balance"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_read_balance_user_not_found() -> None:
    admin = CurrentUser(id=uuid.uuid4(), role=UserRole.admin.value)
    override_dependencies(admin, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/users/{uuid.uuid4()}/balance")

    assert response.status_code == 404
