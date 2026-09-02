from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CharacterStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConversationKind(enum.StrEnum):
    DM = "dm"
    GROUP = "group"


class ConversationStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(enum.StrEnum):
    RECEIVED = "received"
    GENERATING = "generating"
    GENERATED = "generated"
    DELIVERED = "delivered"
    FAILED = "failed"


class MemoryKind(enum.StrEnum):
    USER = "user"
    RELATIONSHIP = "relationship"


class MemoryStatus(enum.StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FORGOTTEN = "forgotten"
    REJECTED = "rejected"


class MemoryScope(enum.StrEnum):
    RELATIONSHIP_PRIVATE = "relationship_private"
    CONVERSATION = "conversation"
    SHAREABLE = "shareable"


class DreamStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MediaJobKind(enum.StrEnum):
    IMAGE = "image"
    AUDIO = "audio"


class MediaJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class DeliveryKind(enum.StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ChannelIdentity(Base):
    __tablename__ = "channel_identities"
    __table_args__ = (UniqueConstraint("channel", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), default="Usuario")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    scenario: Mapped[str] = mapped_column(Text, default="")
    first_mes: Mapped[str] = mapped_column(Text, default="")
    alternate_greetings: Mapped[list[str]] = mapped_column(JSON, default=list)
    mes_example: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    post_history_instructions: Mapped[str] = mapped_column(Text, default="")
    lorebook: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    normalized_card: Mapped[dict[str, Any]] = mapped_column(JSON)
    original_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    original_format: Mapped[str] = mapped_column(String(16))
    original_file_name: Mapped[str] = mapped_column(String(255))
    original_asset_path: Mapped[str] = mapped_column(Text)
    avatar_path: Mapped[str | None] = mapped_column(Text)
    voice_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[CharacterStatus] = mapped_column(
        Enum(CharacterStatus, native_enum=False), default=CharacterStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversation_open", "character_id", "persona_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    external_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[ConversationKind] = mapped_column(
        Enum(ConversationKind, native_enum=False), default=ConversationKind.DM
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, native_enum=False), default=ConversationStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "member_type", "member_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    member_type: Mapped[str] = mapped_column(String(32))
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("channel", "external_id"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False))
    content: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    external_id: Mapped[str] = mapped_column(String(160))
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, native_enum=False), default=MessageStatus.RECEIVED
    )
    model: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    used_dream_allusion: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("character_id", "persona_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"))
    dream_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dream_watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pending_dream_allusion: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    memories: Mapped[list[MemoryItem]] = relationship(back_populates="relationship_record")


class MemoryItem(Base):
    __tablename__ = "memory_items"
    __table_args__ = (Index("ix_memory_prompt", "relationship_id", "status", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    relationship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    kind: Mapped[MemoryKind] = mapped_column(Enum(MemoryKind, native_enum=False))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[MemoryStatus] = mapped_column(
        Enum(MemoryStatus, native_enum=False), default=MemoryStatus.ACTIVE
    )
    scope: Mapped[MemoryScope] = mapped_column(
        Enum(MemoryScope, native_enum=False), default=MemoryScope.RELATIONSHIP_PRIVATE
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(32), default="model")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memory_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    relationship_record: Mapped[Relationship] = relationship(back_populates="memories")
    sources: Mapped[list[MemorySource]] = relationship(back_populates="memory", cascade="all, delete-orphan")


class MemorySource(Base):
    __tablename__ = "memory_sources"
    __table_args__ = (UniqueConstraint("memory_id", "message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memory_items.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    memory: Mapped[MemoryItem] = relationship(back_populates="sources")


class DreamRun(Base):
    __tablename__ = "dream_runs"
    __table_args__ = (UniqueConstraint("relationship_id", "watermark"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    relationship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"))
    watermark: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[DreamStatus] = mapped_column(
        Enum(DreamStatus, native_enum=False), default=DreamStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    share_worthy: Mapped[bool] = mapped_column(Boolean, default=False)
    interestingness: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("relationships.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(255))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int]
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    success: Mapped[bool]
    error_type: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class MediaJob(Base):
    __tablename__ = "media_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    relationship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    kind: Mapped[MediaJobKind] = mapped_column(Enum(MediaJobKind, native_enum=False))
    prompt_or_text: Mapped[str] = mapped_column(Text)
    status: Mapped[MediaJobStatus] = mapped_column(
        Enum(MediaJobStatus, native_enum=False), default=MediaJobStatus.PENDING
    )
    result_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PendingDelivery(Base):
    __tablename__ = "pending_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    kind: Mapped[DeliveryKind] = mapped_column(Enum(DeliveryKind, native_enum=False))
    content_path_or_text: Mapped[str] = mapped_column(Text)
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, native_enum=False), default=DeliveryStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
