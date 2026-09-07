"""publication idempotency

Revision ID: 45d9ee8b602a
Revises: bd14ac8e712f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "45d9ee8b602a"
down_revision: str | None = "bd14ac8e712f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("publication_jobs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=255)))
    op.execute(
        sa.text(
            "UPDATE publication_jobs "
            "SET idempotency_key = 'legacy-publication:' || id "
            "WHERE idempotency_key IS NULL"
        )
    )
    with op.batch_alter_table("publication_jobs") as batch_op:
        batch_op.alter_column("idempotency_key", existing_type=sa.String(length=255), nullable=False)
        batch_op.create_index(
            "ix_publication_jobs_idempotency_key", ["idempotency_key"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("publication_jobs") as batch_op:
        batch_op.drop_index("ix_publication_jobs_idempotency_key")
        batch_op.drop_column("idempotency_key")
