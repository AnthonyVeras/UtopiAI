"""Initial UtopiAI schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def ids() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table("users", *ids())
    op.create_table(
        "channel_identities",
        *ids(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.UniqueConstraint("channel", "external_id"),
    )
    op.create_table(
        "personas",
        *ids(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "characters",
        *ids(),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("first_mes", sa.Text(), nullable=False),
        sa.Column("alternate_greetings", sa.JSON(), nullable=False),
        sa.Column("mes_example", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("post_history_instructions", sa.Text(), nullable=False),
        sa.Column("lorebook", sa.JSON()),
        sa.Column("normalized_card", sa.JSON(), nullable=False),
        sa.Column("original_payload", sa.JSON(), nullable=False),
        sa.Column("original_format", sa.String(16), nullable=False),
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("original_asset_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
    )
    op.create_table(
        "conversations",
        *ids(),
        sa.Column(
            "character_id", sa.Uuid(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("persona_id", sa.Uuid(), sa.ForeignKey("personas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(5), nullable=False),
        sa.Column("status", sa.String(6), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_conversation_open", "conversations", ["character_id", "persona_id", "status"])
    op.create_table(
        "conversation_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("member_type", sa.String(32), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.UniqueConstraint("conversation_id", "member_type", "member_id"),
    )
    op.create_table(
        "relationships",
        *ids(),
        sa.Column(
            "character_id", sa.Uuid(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("persona_id", sa.Uuid(), sa.ForeignKey("personas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dream_due_at", sa.DateTime(timezone=True)),
        sa.Column("last_dream_watermark", sa.DateTime(timezone=True)),
        sa.Column("pending_dream_allusion", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("character_id", "persona_id"),
    )
    op.create_table(
        "messages",
        *ids(),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "character_id", sa.Uuid(), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(9), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(160), nullable=False),
        sa.Column("reply_to_message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("model", sa.String(255)),
        sa.Column("error", sa.Text()),
        sa.Column("used_dream_allusion", sa.Boolean(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("channel", "external_id"),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])
    op.create_table(
        "memory_items",
        *ids(),
        sa.Column(
            "relationship_id",
            sa.Uuid(),
            sa.ForeignKey("relationships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("memory_items.id", ondelete="SET NULL")),
    )
    op.create_index("ix_memory_prompt", "memory_items", ["relationship_id", "status", "kind"])
    op.create_table(
        "memory_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "memory_id", sa.Uuid(), sa.ForeignKey("memory_items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("memory_id", "message_id"),
    )
    op.create_table(
        "dream_runs",
        *ids(),
        sa.Column(
            "relationship_id",
            sa.Uuid(),
            sa.ForeignKey("relationships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("watermark", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("changes", sa.JSON()),
        sa.Column("share_worthy", sa.Boolean(), nullable=False),
        sa.Column("interestingness", sa.Float(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("relationship_id", "watermark"),
    )
    op.create_table(
        "llm_calls",
        *ids(),
        sa.Column("relationship_id", sa.Uuid(), sa.ForeignKey("relationships.id", ondelete="SET NULL")),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_type", sa.String(120)),
    )


def downgrade() -> None:
    for table in (
        "llm_calls",
        "dream_runs",
        "memory_sources",
        "memory_items",
        "messages",
        "relationships",
        "conversation_members",
        "conversations",
        "characters",
        "personas",
        "channel_identities",
        "users",
    ):
        op.drop_table(table)
