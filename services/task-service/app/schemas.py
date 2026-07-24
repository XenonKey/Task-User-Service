import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str
    reward: Decimal = Field(gt=0)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    reward: Decimal
    status: TaskStatus
    performer_id: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
