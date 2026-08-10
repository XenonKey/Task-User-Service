import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_admin
from app.models import User, UserRole
from app.schemas import BalanceOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
async def get_all_users(_: CurrentUser = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[User]:

    result = await db.execute(select(User))
    users = result.scalars().all()

    return users


@router.get("/me", response_model=UserOut)
async def read_me(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/{user_id}/balance", response_model=BalanceOut)
async def read_balance(user_id: uuid.UUID, current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> BalanceOut:
    if current_user.id != user_id and current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return BalanceOut(user_id=user.id, email=user.email, balance=user.balance)
