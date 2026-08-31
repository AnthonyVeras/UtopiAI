from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utopiai.models import (
    DreamRun,
    DreamStatus,
    MemoryItem,
    MemoryKind,
    MemoryScope,
    MemorySource,
    MemoryStatus,
    Relationship,
)


class MemoryError(ValueError):
    pass


async def add_memory(
    session: AsyncSession,
    relationship_id: uuid.UUID,
    kind: MemoryKind,
    content: str,
    *,
    source: str,
    conversation_id: uuid.UUID | None = None,
    evidence_message_ids: list[uuid.UUID] | None = None,
    supersedes_id: uuid.UUID | None = None,
    scope: MemoryScope = MemoryScope.RELATIONSHIP_PRIVATE,
) -> MemoryItem:
    content = " ".join(content.split()).strip()
    if not content or len(content) > 1000:
        raise MemoryError("A memoria deve ter entre 1 e 1000 caracteres")
    duplicate = await session.scalar(
        select(MemoryItem).where(
            MemoryItem.relationship_id == relationship_id,
            MemoryItem.status == MemoryStatus.ACTIVE,
            MemoryItem.kind == kind,
            MemoryItem.content == content,
        )
    )
    if duplicate:
        return duplicate
    replaced = None
    if supersedes_id:
        replaced = await session.scalar(
            select(MemoryItem).where(
                MemoryItem.id == supersedes_id,
                MemoryItem.relationship_id == relationship_id,
                MemoryItem.status == MemoryStatus.ACTIVE,
            )
        )
        if not replaced:
            raise MemoryError("Memoria substituida nao existe ou nao esta ativa")
    memory = MemoryItem(
        relationship_id=relationship_id,
        conversation_id=conversation_id,
        kind=kind,
        content=content,
        source=source,
        scope=scope,
        supersedes_id=supersedes_id,
    )
    session.add(memory)
    await session.flush()
    for message_id in dict.fromkeys(evidence_message_ids or []):
        session.add(MemorySource(memory_id=memory.id, message_id=message_id))
    if replaced:
        replaced.status = MemoryStatus.SUPERSEDED
        replaced.valid_until = memory.valid_from
    return memory


async def forget_memory(session: AsyncSession, relationship_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
    memory = await session.scalar(
        select(MemoryItem).where(
            MemoryItem.id == memory_id,
            MemoryItem.relationship_id == relationship_id,
            MemoryItem.status == MemoryStatus.ACTIVE,
        )
    )
    if not memory:
        return False
    memory.status = MemoryStatus.FORGOTTEN
    return True


async def active_memories(session: AsyncSession, relationship_id: uuid.UUID) -> list[MemoryItem]:
    result = await session.scalars(
        select(MemoryItem)
        .where(
            MemoryItem.relationship_id == relationship_id,
            MemoryItem.status == MemoryStatus.ACTIVE,
        )
        .order_by(MemoryItem.kind, MemoryItem.importance.desc(), MemoryItem.created_at)
    )
    return list(result)


def render_memory_markdown(title: str, active: list[MemoryItem], historical: list[MemoryItem]) -> str:
    current = "\n".join(f"- [{item.id}] {item.content}" for item in active) or "- Nenhuma."
    history = (
        "\n".join(f"- [{item.id}] ({item.status.value}) {item.content}" for item in historical)
        or "- Nenhuma."
    )
    return f"# {title}\n\n## Estado vigente\n\n{current}\n\n## Historico\n\n{history}\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


async def regenerate_vault(session: AsyncSession, data_dir: Path, relationship: Relationship) -> Path:
    memories = list(
        await session.scalars(
            select(MemoryItem)
            .where(MemoryItem.relationship_id == relationship.id)
            .order_by(MemoryItem.created_at)
        )
    )
    dreams = list(
        await session.scalars(
            select(DreamRun)
            .where(
                DreamRun.relationship_id == relationship.id,
                DreamRun.status == DreamStatus.SUCCEEDED,
            )
            .order_by(DreamRun.created_at.desc())
        )
    )
    base = (
        data_dir / "vaults" / str(relationship.character_id) / "relationships" / str(relationship.persona_id)
    )
    for kind, filename, title in (
        (MemoryKind.USER, "usuario.md", "Usuario"),
        (MemoryKind.RELATIONSHIP, "relacionamento.md", "Relacionamento"),
    ):
        matching = [item for item in memories if item.kind == kind]
        atomic_write(
            base / filename,
            render_memory_markdown(
                title,
                [item for item in matching if item.status == MemoryStatus.ACTIVE],
                [item for item in matching if item.status != MemoryStatus.ACTIVE],
            ),
        )
    dream_text = "\n\n".join(
        f"## {run.finished_at or run.created_at}\n\n{run.summary or 'Sem resumo.'}" for run in dreams
    )
    atomic_write(base / "sonhos.md", f"# Sonhos\n\n{dream_text or 'Nenhum sonho concluido.'}\n")
    return base
