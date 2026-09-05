"""complete the Phase 2A content engine schema

Revision ID: 9c7a2e41f5b8
Revises: 4e82f6219c10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c7a2e41f5b8"
down_revision: str | None = "4e82f6219c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_candidates",
        sa.Column(
            "duplicate_classification",
            sa.String(length=32),
            nullable=False,
            server_default="NEW",
        ),
    )
    op.add_column(
        "content_packs",
        sa.Column("status", sa.String(length=24), nullable=False, server_default="REVIEW"),
    )
    op.add_column(
        "content_packs",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "media_assets", sa.Column("original_filename", sa.String(length=500), nullable=True)
    )
    with op.batch_alter_table("pack_items") as batch_op:
        batch_op.add_column(sa.Column("source_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("source_external_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_reference", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("original_filename", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.create_foreign_key(
            "fk_pack_items_source_id_sources", "sources", ["source_id"], ["id"]
        )
        batch_op.create_index("ix_pack_items_source_id", ["source_id"], unique=False)
        batch_op.create_index(
            "ix_pack_items_source_external_id", ["source_external_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("pack_items") as batch_op:
        batch_op.drop_index("ix_pack_items_source_external_id")
        batch_op.drop_index("ix_pack_items_source_id")
        batch_op.drop_constraint("fk_pack_items_source_id_sources", type_="foreignkey")
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("source_reference")
        batch_op.drop_column("source_external_id")
        batch_op.drop_column("source_id")
    op.drop_column("media_assets", "original_filename")
    op.drop_column("content_packs", "metadata_json")
    op.drop_column("content_packs", "status")
    op.drop_column("content_candidates", "duplicate_classification")
