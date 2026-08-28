"""add active state to copy slots

Revision ID: 4e82f6219c10
Revises: ef39cde4b9c4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4e82f6219c10"
down_revision: str | None = "ef39cde4b9c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "copy_slots",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("copy_slots", "active")
