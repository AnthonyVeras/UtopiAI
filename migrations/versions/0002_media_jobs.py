"""Add media support: avatar_path, voice_id, media_jobs, pending_deliveries.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("avatar_path", sa.Text()))
    op.add_column("characters", sa.Column("voice_id", sa.String(64)))
    op.create_table(
        "media_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "character_id", sa.Uuid(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "relationship_id",
            sa.Uuid(),
            sa.ForeignKey("relationships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(5), nullable=False),
        sa.Column("prompt_or_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(7), nullable=False, server_default="pending"),
        sa.Column("result_path", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_media_jobs_pending", "media_jobs", ["status", "created_at"])
    op.create_table(
        "pending_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(5), nullable=False),
        sa.Column("content_path_or_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(9), nullable=False, server_default="pending"),
    )
    op.create_index("ix_pending_deliveries_pending", "pending_deliveries", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("pending_deliveries")
    op.drop_table("media_jobs")
    op.drop_column("characters", "voice_id")
    op.drop_column("characters", "avatar_path")
