from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from utopiai.cards import NormalizedCard, load_card, store_original
from utopiai.config import Settings
from utopiai.llm import LLMResult, complete
from utopiai.memory import (
    active_memories,
    add_memory,
    forget_memory,
    regenerate_vault,
)
from utopiai.models import (
    ChannelIdentity,
    Character,
    CharacterStatus,
    Conversation,
    ConversationMember,
    ConversationStatus,
    DreamRun,
    LLMCall,
    MemoryKind,
    Message,
    MessageRole,
    MessageStatus,
    Persona,
    Relationship,
    User,
    now_utc,
)
from utopiai.prompting import REMEMBER_TOOL, PromptInput, PromptMemory, build_prompt


class NotReadyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeContext:
    user: User
    persona: Persona
    character: Character
    relationship: Relationship
    conversation: Conversation


@dataclass(frozen=True)
class GeneratedReply:
    message_id: uuid.UUID
    text: str
    duplicate: bool = False


class ConversationService:
    def __init__(self, settings: Settings, sessions: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.sessions = sessions

    async def ensure_identity(self, session: AsyncSession, telegram_id: int) -> tuple[User, Persona]:
        identity = await session.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "telegram",
                ChannelIdentity.external_id == str(telegram_id),
            )
        )
        if identity:
            user = await session.get(User, identity.user_id)
        else:
            user = User()
            session.add(user)
            await session.flush()
            session.add(ChannelIdentity(user_id=user.id, channel="telegram", external_id=str(telegram_id)))
        persona = await session.scalar(
            select(Persona).where(Persona.user_id == user.id, Persona.is_active.is_(True))
        )
        if not persona:
            persona = Persona(user_id=user.id)
            session.add(persona)
            await session.flush()
        return user, persona

    async def _context(self, session: AsyncSession, telegram_id: int, chat_id: int) -> RuntimeContext:
        user, persona = await self.ensure_identity(session, telegram_id)
        character = await session.scalar(
            select(Character).where(Character.owner_id == user.id, Character.status == CharacterStatus.ACTIVE)
        )
        if not character:
            raise NotReadyError("Importe um Character Card com /importar antes de conversar.")
        relationship = await session.scalar(
            select(Relationship).where(
                Relationship.character_id == character.id, Relationship.persona_id == persona.id
            )
        )
        if not relationship:
            relationship = Relationship(character_id=character.id, persona_id=persona.id)
            session.add(relationship)
            await session.flush()
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.character_id == character.id,
                Conversation.persona_id == persona.id,
                Conversation.channel == "telegram",
                Conversation.external_id == str(chat_id),
                Conversation.status == ConversationStatus.OPEN,
            )
        )
        if not conversation:
            conversation = Conversation(
                character_id=character.id,
                persona_id=persona.id,
                external_id=str(chat_id),
            )
            session.add(conversation)
            await session.flush()
            session.add_all(
                [
                    ConversationMember(
                        conversation_id=conversation.id, member_type="user", member_id=user.id
                    ),
                    ConversationMember(
                        conversation_id=conversation.id,
                        member_type="character",
                        member_id=character.id,
                    ),
                ]
            )
        return RuntimeContext(user, persona, character, relationship, conversation)

    async def import_character(
        self, telegram_id: int, chat_id: int, filename: str, blob: bytes
    ) -> tuple[Character, NormalizedCard, uuid.UUID | None]:
        card = load_card(blob, filename)
        async with self.sessions.begin() as session:
            user, persona = await self.ensure_identity(session, telegram_id)
            await session.execute(
                update(Character)
                .where(Character.owner_id == user.id, Character.status == CharacterStatus.ACTIVE)
                .values(status=CharacterStatus.ARCHIVED)
            )
            character_id = uuid.uuid4()
            asset = store_original(blob, filename, self.settings.data_dir / "cards", str(character_id))
            character = Character(
                id=character_id,
                owner_id=user.id,
                name=card.name,
                description=card.description,
                personality=card.personality,
                scenario=card.scenario,
                first_mes=card.first_mes,
                alternate_greetings=card.alternate_greetings,
                mes_example=card.mes_example,
                system_prompt=card.system_prompt,
                post_history_instructions=card.post_history_instructions,
                lorebook=card.lorebook,
                normalized_card=card.payload,
                original_payload=card.original_payload,
                original_format=card.original_format,
                original_file_name=filename,
                original_asset_path=str(asset),
            )
            session.add(character)
            await session.flush()
            relationship = Relationship(character_id=character.id, persona_id=persona.id)
            session.add(relationship)
            await session.flush()
            conversation = Conversation(
                character_id=character.id,
                persona_id=persona.id,
                external_id=str(chat_id),
            )
            session.add(conversation)
            await session.flush()
            session.add_all(
                [
                    ConversationMember(
                        conversation_id=conversation.id, member_type="user", member_id=user.id
                    ),
                    ConversationMember(
                        conversation_id=conversation.id,
                        member_type="character",
                        member_id=character.id,
                    ),
                ]
            )
            first_message_id = None
            if character.first_mes:
                first_message = Message(
                    conversation_id=conversation.id,
                    character_id=character.id,
                    user_id=user.id,
                    role=MessageRole.ASSISTANT,
                    content=character.first_mes,
                    external_id=f"import:{character.id}:first",
                    status=MessageStatus.GENERATED,
                )
                session.add(first_message)
                await session.flush()
                first_message_id = first_message.id
            await regenerate_vault(session, self.settings.data_dir, relationship)
        return character, card, first_message_id

    async def converse(
        self, telegram_id: int, chat_id: int, external_message_id: str, content: str
    ) -> GeneratedReply:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"conversation:{ctx.conversation.id}"},
            )
            existing = await session.scalar(
                select(Message).where(
                    Message.channel == "telegram", Message.external_id == external_message_id
                )
            )
            if existing:
                reply = await session.scalar(
                    select(Message).where(Message.reply_to_message_id == existing.id)
                )
                if reply:
                    return GeneratedReply(reply.id, reply.content, duplicate=True)
                raise NotReadyError("Essa mensagem ja esta sendo processada.")
            user_message = Message(
                conversation_id=ctx.conversation.id,
                character_id=ctx.character.id,
                user_id=ctx.user.id,
                role=MessageRole.USER,
                content=content,
                external_id=external_message_id,
                status=MessageStatus.RECEIVED,
            )
            session.add(user_message)
            ctx.relationship.dream_due_at = now_utc() + timedelta(hours=6)
            await session.flush()
            history_rows = list(
                await session.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == ctx.conversation.id,
                        Message.id != user_message.id,
                        Message.status != MessageStatus.FAILED,
                    )
                    .order_by(Message.created_at.desc())
                    .limit(80)
                )
            )
            memories = await active_memories(session, ctx.relationship.id)
            use_allusion = ctx.relationship.pending_dream_allusion and secrets.randbelow(5) == 0
            prompt = build_prompt(
                PromptInput(
                    character=ctx.character,
                    persona_name=ctx.persona.name,
                    persona_description=ctx.persona.description,
                    memories=[PromptMemory(item.kind, item.content) for item in memories],
                    history=[(item.role.value, item.content) for item in reversed(history_rows)],
                    current_message=content,
                    dream_allusion=use_allusion,
                ),
                self.settings.chat_profile.context_window,
                self.settings.chat_profile.max_output_tokens,
            )
            try:
                result, used_tools = await self._chat_with_memory_tools(session, ctx, user_message, prompt)
            except Exception as exc:
                user_message.status = MessageStatus.FAILED
                user_message.error = f"{type(exc).__name__}: {exc}"[:2000]
                await session.commit()
                raise
            answer = result.content.strip() or "..."
            assistant = Message(
                conversation_id=ctx.conversation.id,
                character_id=ctx.character.id,
                user_id=ctx.user.id,
                role=MessageRole.ASSISTANT,
                content=answer,
                external_id=f"reply:{external_message_id}",
                reply_to_message_id=user_message.id,
                status=MessageStatus.GENERATED,
                model=self.settings.chat_profile.model,
                used_dream_allusion=use_allusion,
            )
            session.add(assistant)
            user_message.status = MessageStatus.GENERATED
            await session.flush()
            if used_tools:
                await regenerate_vault(session, self.settings.data_dir, ctx.relationship)
            return GeneratedReply(assistant.id, answer)

    async def _chat_with_memory_tools(
        self,
        session: AsyncSession,
        ctx: RuntimeContext,
        source_message: Message,
        prompt: list[dict[str, Any]],
    ) -> tuple[LLMResult, bool]:
        profile = self.settings.chat_profile
        tools_enabled = profile.supports_tools is not False
        try:
            result = await complete(profile, prompt, tools=[REMEMBER_TOOL] if tools_enabled else None)
        except Exception as exc:
            self._record_failed_call(session, ctx.relationship.id, source_message.id, exc)
            if not tools_enabled:
                raise
            try:
                result = await complete(profile, prompt)
            except Exception as fallback_exc:
                self._record_failed_call(session, ctx.relationship.id, source_message.id, fallback_exc)
                raise
            tools_enabled = False
        self._record_call(session, ctx.relationship.id, source_message.id, "chat", result)
        if not result.tool_calls:
            return result, False
        tool_messages: list[dict[str, Any]] = []
        valid_calls = [call for call in result.tool_calls if call["name"] == "lembrar"][:4]
        prompt.append(
            {
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                        },
                    }
                    for call in valid_calls
                ],
            }
        )
        for call in valid_calls:
            args = call["arguments"]
            if args.get("tipo") not in {"usuario", "relacionamento"}:
                continue
            kind = MemoryKind.USER if args.get("tipo") == "usuario" else MemoryKind.RELATIONSHIP
            supersedes = args.get("substitui_id")
            memory = await add_memory(
                session,
                ctx.relationship.id,
                kind,
                str(args.get("fato", "")),
                source="model",
                conversation_id=ctx.conversation.id,
                evidence_message_ids=[source_message.id],
                supersedes_id=uuid.UUID(supersedes) if supersedes else None,
            )
            tool_messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": f"salvo:{memory.id}"}
            )
        prompt.extend(tool_messages)
        final = await complete(profile, prompt, tools=[REMEMBER_TOOL])
        self._record_call(session, ctx.relationship.id, source_message.id, "chat", final)
        return final, bool(valid_calls)

    def _record_call(
        self,
        session: AsyncSession,
        relationship_id: uuid.UUID,
        message_id: uuid.UUID | None,
        role: str,
        result: LLMResult,
    ) -> None:
        session.add(
            LLMCall(
                relationship_id=relationship_id,
                message_id=message_id,
                role=role,
                model=self.settings.chat_profile.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                estimated_cost=result.estimated_cost,
                success=True,
            )
        )

    def _record_failed_call(
        self,
        session: AsyncSession,
        relationship_id: uuid.UUID,
        message_id: uuid.UUID | None,
        error: Exception,
    ) -> None:
        session.add(
            LLMCall(
                relationship_id=relationship_id,
                message_id=message_id,
                role="chat",
                model=self.settings.chat_profile.model,
                latency_ms=0,
                success=False,
                error_type=type(error).__name__,
            )
        )

    async def mark_delivered(self, message_id: uuid.UUID) -> None:
        async with self.sessions.begin() as session:
            message = await session.get(Message, message_id)
            if not message:
                return
            message.status = MessageStatus.DELIVERED
            message.delivered_at = now_utc()
            if message.used_dream_allusion:
                conversation = await session.get(Conversation, message.conversation_id)
                relationship = await session.scalar(
                    select(Relationship).where(
                        Relationship.character_id == message.character_id,
                        Relationship.persona_id == conversation.persona_id,
                    )
                )
                if relationship:
                    relationship.pending_dream_allusion = False

    async def new_conversation(self, telegram_id: int, chat_id: int) -> None:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            ctx.conversation.status = ConversationStatus.CLOSED
            ctx.conversation.closed_at = now_utc()

    async def set_persona(
        self, telegram_id: int, name: str | None = None, description: str | None = None
    ) -> Persona:
        async with self.sessions.begin() as session:
            _, persona = await self.ensure_identity(session, telegram_id)
            if name is not None:
                persona.name = name.strip()[:120] or persona.name
            if description is not None:
                persona.description = description.strip()[:4000]
            return persona

    async def active_context(self, telegram_id: int, chat_id: int) -> RuntimeContext:
        async with self.sessions.begin() as session:
            return await self._context(session, telegram_id, chat_id)

    async def list_memories(self, telegram_id: int, chat_id: int) -> tuple[RuntimeContext, list]:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            return ctx, await active_memories(session, ctx.relationship.id)

    async def remember_manual(
        self, telegram_id: int, chat_id: int, kind: MemoryKind, content: str
    ) -> uuid.UUID:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            memory = await add_memory(session, ctx.relationship.id, kind, content, source="manual")
            await session.flush()
            await regenerate_vault(session, self.settings.data_dir, ctx.relationship)
            return memory.id

    async def forget(self, telegram_id: int, chat_id: int, memory_id: uuid.UUID) -> bool:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            forgotten = await forget_memory(session, ctx.relationship.id, memory_id)
            if forgotten:
                await session.flush()
                await regenerate_vault(session, self.settings.data_dir, ctx.relationship)
            return forgotten

    async def export_character(self, telegram_id: int, chat_id: int) -> tuple[Character, bytes, bytes]:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            original = await asyncio.to_thread(Path(ctx.character.original_asset_path).read_bytes)
            normalized = json.dumps(ctx.character.normalized_card, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )
            return ctx.character, original, normalized

    async def recent_dreams(self, telegram_id: int, chat_id: int, limit: int = 5) -> list[DreamRun]:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            return list(
                await session.scalars(
                    select(DreamRun)
                    .where(DreamRun.relationship_id == ctx.relationship.id)
                    .order_by(DreamRun.created_at.desc())
                    .limit(limit)
                )
            )

    async def retry_last(self, telegram_id: int, chat_id: int, retry_external_id: str) -> GeneratedReply:
        async with self.sessions() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            failed = await session.scalar(
                select(Message)
                .where(
                    Message.conversation_id == ctx.conversation.id,
                    Message.role == MessageRole.USER,
                    Message.status == MessageStatus.FAILED,
                )
                .order_by(Message.created_at.desc())
            )
            if not failed:
                raise NotReadyError("Nao ha geracao falha para repetir.")
            content = failed.content
        return await self.converse(telegram_id, chat_id, retry_external_id, content)

    async def delete_current_conversation(self, telegram_id: int, chat_id: int) -> None:
        async with self.sessions.begin() as session:
            ctx = await self._context(session, telegram_id, chat_id)
            await session.delete(ctx.conversation)

    async def delete_everything(self, telegram_id: int) -> None:
        paths: list[Path] = []
        async with self.sessions.begin() as session:
            identity = await session.scalar(
                select(ChannelIdentity).where(
                    ChannelIdentity.channel == "telegram",
                    ChannelIdentity.external_id == str(telegram_id),
                )
            )
            if not identity:
                return
            characters = list(
                await session.scalars(select(Character).where(Character.owner_id == identity.user_id))
            )
            paths = [Path(character.original_asset_path).parent for character in characters]
            paths.extend(self.settings.data_dir / "vaults" / str(character.id) for character in characters)
            await session.delete(await session.get(User, identity.user_id))
        allowed_roots = [
            (self.settings.data_dir / "cards").resolve(),
            (self.settings.data_dir / "vaults").resolve(),
        ]
        for path in paths:
            resolved = path.resolve()
            if any(resolved.is_relative_to(root) for root in allowed_roots) and resolved.exists():
                shutil.rmtree(resolved)
