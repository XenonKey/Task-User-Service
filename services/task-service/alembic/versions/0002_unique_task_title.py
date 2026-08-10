"""unique constraint on tasks.title

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM tasks
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY title ORDER BY created_at) AS rn
                FROM tasks
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )
    op.create_unique_constraint("uq_tasks_title", "tasks", ["title"])


def downgrade() -> None:
    op.drop_constraint("uq_tasks_title", "tasks", type_="unique")
