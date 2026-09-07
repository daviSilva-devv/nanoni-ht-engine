"""persisted publication plans

Revision ID: 9af4f0aa31d8
Revises: 45d9ee8b602a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9af4f0aa31d8"
down_revision: str | None = "45d9ee8b602a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publication_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("planning_date", sa.Date(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("publication_job_id", sa.String(length=36)),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_job_id"], ["publication_jobs.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["publication_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "planning_date", "slot_index", name="uq_plan_rule_day_slot"),
    )
    op.create_index("ix_publication_plans_planning_date", "publication_plans", ["planning_date"])
    op.create_index(
        "ix_publication_plans_publication_job_id",
        "publication_plans",
        ["publication_job_id"],
        unique=True,
    )
    op.create_index("ix_publication_plans_rule_id", "publication_plans", ["rule_id"])
    op.create_index("ix_publication_plans_scheduled_for", "publication_plans", ["scheduled_for"])


def downgrade() -> None:
    op.drop_index("ix_publication_plans_scheduled_for", table_name="publication_plans")
    op.drop_index("ix_publication_plans_rule_id", table_name="publication_plans")
    op.drop_index("ix_publication_plans_publication_job_id", table_name="publication_plans")
    op.drop_index("ix_publication_plans_planning_date", table_name="publication_plans")
    op.drop_table("publication_plans")
