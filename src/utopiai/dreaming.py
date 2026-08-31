from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from utopiai.config import Settings
from utopiai.llm import LLMResult, complete
from utopiai.memory import active_memories, add_memory, regenerate_vault
from utopiai.models import (
    Conversation,
    DreamRun,
    DreamStatus,
    LLMCall,
    MemoryItem,
    MemoryKind,
    MemoryStatus,
    Message,
    MessageRole,
    Relationship,
    now_utc,
)

DREAM_SYSTEM = """Voce consolida memoria de longo prazo de um RP.
Use somente fatos sustentados pelas mensagens fornecidas. Nao invente e nao transforme inferencia em fato.
Atualize contradicoes com supersede; una repeticoes; prefira noop a uma memoria fraca.
Responda exclusivamente com JSON no schema pedido."""


class DreamPlanError(ValueError):
    pass


def validate_plan(raw: str, evidence_ids: set[uuid.UUID]) -> dict[str, Any]:
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DreamPlanError(f"JSON invalido: {exc}") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("changes", []), list):
        raise DreamPlanError("Plano sem lista changes")
    if not isinstance(plan.get("summary", ""), str):
        raise DreamPlanError("summary deve ser string")
    interestingness = float(plan.get("interestingness", 0.0))
    if not 0 <= interestingness <= 1:
        raise DreamPlanError("interestingness fora de 0..1")
    for change in plan.get("changes", []):
        if not isinstance(change, dict) or change.get("operation") not in {
            "add",
            "supersede",
            "noop",
        }:
            raise DreamPlanError("Operacao de memoria invalida")
        if change.get("operation") == "noop":
            continue
        if change.get("kind") not in {"user", "relationship"}:
            raise DreamPlanError("Tipo de memoria invalido")
        if not str(change.get("content", "")).strip():
            raise DreamPlanError("Memoria sem conteudo")
        try:
            cited = {uuid.UUID(value) for value in change.get("evidence_message_ids", [])}
        except (TypeError, ValueError) as exc:
            raise DreamPlanError("ID de evidencia invalido") from exc
        if not cited or not cited.issubset(evidence_ids):
            raise DreamPlanError("Evidencia ausente ou fora do watermark")
        if change["operation"] == "supersede" and not change.get("supersedes_id"):
            raise DreamPlanError("Supersede sem referencia")
    plan["interestingness"] = interestingness
    plan["share_worthy"] = bool(plan.get("share_worthy", False))
    return plan


def dream_messages(messages: list[Message], memories: list[MemoryItem]) -> list[dict[str, str]]:
    memory_text = (
        "\n".join(f"[{item.id}] {item.kind.value}: {item.content}" for item in memories)
        or "Nenhuma memoria vigente."
    )
    transcript = "\n".join(f"[{message.id}] {message.role.value}: {message.content}" for message in messages)
    schema = {
        "summary": "string",
        "share_worthy": True,
        "interestingness": 0.0,
        "changes": [
            {
                "operation": "add | supersede | noop",
                "kind": "user | relationship",
                "content": "string",
                "supersedes_id": None,
                "evidence_message_ids": [],
            }
        ],
    }
    return [
        {"role": "system", "content": DREAM_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Memorias vigentes:\n{memory_text}\n\nMensagens novas:\n{transcript}\n\n"
                f"Schema obrigatorio:\n{json.dumps(schema, ensure_ascii=False)}"
            ),
        },
    ]


class DreamWorker:
    def __init__(self, settings: Settings, sessions: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.sessions = sessions

    async def run_one_due(self) -> bool:
        async with self.sessions.begin() as session:
            relationship = await session.scalar(
                select(Relationship)
                .where(
                    Relationship.dream_due_at.is_not(None),
                    Relationship.dream_due_at <= now_utc(),
                )
                .order_by(Relationship.dream_due_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not relationship:
                return False
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"dream:{relationship.id}"},
            )
            await self.run_relationship(session, relationship)
            return True

    async def run_relationship(
        self, session: AsyncSession, relationship: Relationship, *, force: bool = False
    ) -> DreamRun | None:
        query = (
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.character_id == relationship.character_id,
                Conversation.persona_id == relationship.persona_id,
                Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
            )
            .order_by(Message.created_at)
        )
        if relationship.last_dream_watermark:
            query = query.where(Message.created_at > relationship.last_dream_watermark)
        messages = list(await session.scalars(query))
        if not messages:
            relationship.dream_due_at = None
            return None
        watermark = messages[-1].created_at
        existing = await session.scalar(
            select(DreamRun).where(
                DreamRun.relationship_id == relationship.id, DreamRun.watermark == watermark
            )
        )
        if existing and existing.status == DreamStatus.SUCCEEDED:
            relationship.dream_due_at = None
            return existing
        run = existing or DreamRun(relationship_id=relationship.id, watermark=watermark)
        session.add(run)
        run.status = DreamStatus.RUNNING
        memories = await active_memories(session, relationship.id)
        prompt = dream_messages(messages, memories)
        result: LLMResult | None = None
        plan: dict[str, Any] | None = None
        last_error: Exception | None = None
        for attempt in range(1, 4):
            run.attempts = attempt
            try:
                result = await complete(
                    self.settings.dream_profile,
                    prompt,
                    response_format={"type": "json_object"},
                )
                plan = validate_plan(result.content, {message.id for message in messages})
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt - 1))
        if result:
            session.add(
                LLMCall(
                    relationship_id=relationship.id,
                    role="dream",
                    model=self.settings.dream_profile.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    estimated_cost=result.estimated_cost,
                    success=plan is not None,
                    error_type=type(last_error).__name__ if plan is None and last_error else None,
                )
            )
        if plan is None:
            run.status = DreamStatus.FAILED
            run.error = f"{type(last_error).__name__}: {last_error}"[:2000]
            run.finished_at = now_utc()
            relationship.dream_due_at = now_utc() + timedelta(minutes=30)
            return run
        applied: list[dict[str, Any]] = []
        for change in plan["changes"]:
            if change["operation"] == "noop":
                continue
            supersedes = change.get("supersedes_id")
            try:
                memory = await add_memory(
                    session,
                    relationship.id,
                    MemoryKind(change["kind"]),
                    change["content"],
                    source="dream",
                    evidence_message_ids=[uuid.UUID(value) for value in change["evidence_message_ids"]],
                    supersedes_id=uuid.UUID(supersedes) if supersedes else None,
                )
                applied.append({**change, "memory_id": str(memory.id)})
            except Exception as exc:
                rejected = MemoryItem(
                    relationship_id=relationship.id,
                    kind=MemoryKind(change["kind"]),
                    content=change["content"][:1000],
                    status=MemoryStatus.REJECTED,
                    source="dream",
                )
                session.add(rejected)
                applied.append({**change, "rejected": str(exc)})
        run.status = DreamStatus.SUCCEEDED
        run.summary = plan.get("summary", "")
        run.changes = applied
        run.share_worthy = plan["share_worthy"]
        run.interestingness = plan["interestingness"]
        run.finished_at = now_utc()
        relationship.last_dream_watermark = watermark
        relationship.dream_due_at = None
        if run.share_worthy:
            relationship.pending_dream_allusion = True
        await session.flush()
        await regenerate_vault(session, self.settings.data_dir, relationship)
        return run

    async def recover_stale(self) -> int:
        cutoff = now_utc() - timedelta(minutes=20)
        async with self.sessions.begin() as session:
            stale = list(
                await session.scalars(
                    select(DreamRun).where(
                        DreamRun.status == DreamStatus.RUNNING, DreamRun.created_at < cutoff
                    )
                )
            )
            for run in stale:
                run.status = DreamStatus.FAILED
                run.error = "Execucao interrompida; recuperada pela auditoria."
                run.finished_at = now_utc()
                relationship = await session.get(Relationship, run.relationship_id)
                if relationship:
                    relationship.dream_due_at = now_utc()
            return len(stale)
