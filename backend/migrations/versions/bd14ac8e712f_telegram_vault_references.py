"""add Telegram vault references to media assets

Revision ID: bd14ac8e712f
Revises: 9c7a2e41f5b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bd14ac8e712f"
down_revision: str | None = "9c7a2e41f5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("vault_chat_id", sa.String(length=64)))
    op.create_index("ix_media_assets_vault_chat_id", "media_assets", ["vault_chat_id"])


def downgrade() -> None:
    op.drop_index("ix_media_assets_vault_chat_id", table_name="media_assets")
    op.drop_column("media_assets", "vault_chat_id")
