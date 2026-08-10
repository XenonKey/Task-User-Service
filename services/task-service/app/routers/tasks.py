import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_admin
from app.db import get_db
from app.models import Outbox, Task, TaskStatus
from app.schemas import TaskCreate, TaskOut

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_task_or_404(db: AsyncSession, task_id: uuid.UUID) -> Task:
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> Task:
    task = Task(title=data.title, description=data.description, reward=data.reward)
    db.add(task)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task with this title already exists")
    await db.refresh(task)
    return task


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None), db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)
) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/my", response_model=list[TaskOut])
async def my_list_tasks(db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> list[Task]:

    stmt = select(Task).where(Task.performer_id == current_user.id).order_by(Task.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{task_id}/claim", response_model=TaskOut)
async def claim_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> Task:
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.status == TaskStatus.OPEN)
        .values(status=TaskStatus.IN_PROGRESS, performer_id=current_user.id, version=Task.version + 1)
        .returning(Task.id)
    )
    result = await db.execute(stmt)

    claimed = result.first() is not None
    if not claimed:
        await db.rollback()
        existing = await _get_task_or_404(db, task_id)
        if existing.status != TaskStatus.OPEN:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task already claimed")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not open")
    await db.commit()
    return await _get_task_or_404(db, task_id)


@router.post("/{task_id}/complete", response_model=TaskOut)
async def complete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> Task:
    task = await _get_task_or_404(db, task_id)
    if task.performer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not in progress")
    task.status = TaskStatus.DONE
    task.version += 1
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/{task_id}/approve", response_model=TaskOut)
async def approve_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> Task:
    task = await _get_task_or_404(db, task_id)
    if task.status != TaskStatus.DONE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not done")
    task.status = TaskStatus.APPROVED
    task.version += 1
    db.add(
        Outbox(
            aggregate_id=task.id,
            event_type="task.completed",
            payload={
                "task_id": str(task.id),
                "performer_id": str(task.performer_id),
                "reward": str(task.reward),
            },
        )
    )
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/{task_id}/reject", response_model=TaskOut)
async def reject_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(require_admin)) -> Task:
    task = await _get_task_or_404(db, task_id)
    if task.status != TaskStatus.DONE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not done")
    task.status = TaskStatus.REJECTED
    task.version += 1
    await db.commit()
    await db.refresh(task)
    return task
