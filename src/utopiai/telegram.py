from __future__ import annotations

import asyncio
import io
import logging
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from utopiai.config import Settings
from utopiai.db import session_factory
from utopiai.dreaming import DreamWorker
from utopiai.logging import configure_logging
from utopiai.models import (
    Conversation,
    DeliveryKind,
    DeliveryStatus,
    DreamRun,
    MemoryKind,
    PendingDelivery,
    Relationship,
)
from utopiai.service import ConversationService, NotReadyError

logger = logging.getLogger(__name__)
TELEGRAM_TEXT_LIMIT = 4096
CARD_PHOTO_HINT = (
    "Envie o PNG como arquivo/documento, nao como foto. "
    "O Telegram remove os metadados do Character Card ao comprimir imagens."
)


def split_text(value: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks or [""]


class TelegramAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions = session_factory(settings.database_url)
        self.service = ConversationService(settings, self.sessions)
        self.dreams = DreamWorker(settings, self.sessions)

    def allowed(self, update: Update) -> bool:
        return bool(
            update.effective_user
            and update.effective_user.id in self.settings.telegram_allowed_user_ids
            and update.effective_chat
            and update.effective_chat.type == "private"
        )

    async def guard(self, update: Update) -> bool:
        if self.allowed(update):
            return True
        if update.effective_message:
            await update.effective_message.reply_text("Acesso nao autorizado.")
        return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        try:
            ctx = await self.service.active_context(update.effective_user.id, update.effective_chat.id)
            active = f"Personagem ativo: {ctx.character.name}."
        except NotReadyError:
            active = "Nenhum personagem ativo."
        await update.effective_message.reply_text(
            f"UtopiAI v0.1\n{active}\nUse /importar e envie um Character Card JSON ou PNG."
        )

    async def importar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        context.user_data["awaiting_card"] = True
        await update.effective_message.reply_text(
            "Envie agora o card .json ou .png como arquivo/documento (maximo 10 MB)."
        )

    async def photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        if context.user_data.get("awaiting_card", False):
            await update.effective_message.reply_text(CARD_PHOTO_HINT)
            return
        # Vision input: download photo and pass to conversation
        if not self.settings.chat_profile.supports_vision:
            await update.effective_message.reply_text(
                "Este personagem nao possui visao habilitada no momento."
            )
            return
        try:
            photo = update.effective_message.photo[-1]  # largest resolution
            telegram_file = await photo.get_file()
            photo_bytes = bytes(await telegram_file.download_as_bytearray())
            caption = update.effective_message.caption or ""
            reply = await self.service.converse_with_image(
                update.effective_user.id,
                update.effective_chat.id,
                f"{update.effective_chat.id}:{update.effective_message.message_id}",
                caption,
                photo_bytes,
            )
            for chunk in split_text(reply.text):
                await update.effective_message.reply_text(chunk)
            await self.service.mark_delivered(reply.message_id)
        except NotReadyError as exc:
            await update.effective_message.reply_text(str(exc))
        except Exception:
            logger.exception("vision_message_failed")
            await update.effective_message.reply_text("A geracao falhou. Use /repetir para tentar de novo.")

    async def document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update) or not context.user_data.pop("awaiting_card", False):
            return
        document = update.effective_message.document
        if document.file_size and document.file_size > 10 * 1024 * 1024:
            await update.effective_message.reply_text("Arquivo acima do limite de 10 MB.")
            return
        try:
            telegram_file = await document.get_file()
            blob = bytes(await telegram_file.download_as_bytearray())
            character, card, first_message_id = await self.service.import_character(
                update.effective_user.id,
                update.effective_chat.id,
                document.file_name or "character.json",
                blob,
            )
        except Exception as exc:
            logger.exception("card_import_failed")
            await update.effective_message.reply_text(f"Nao foi possivel importar o card: {exc}")
            return
        warning = "\n".join(card.compatibility_warnings)
        voice_msg = f"\nVoz: {character.voice_id}. Use /voz <id> para trocar." if character.voice_id else ""
        avatar_msg = "\nAvatar extraido do card." if character.avatar_path else ""
        await update.effective_message.reply_text(
            f"{character.name} foi importado com sucesso.{avatar_msg}{voice_msg}"
            + (f"\n{warning}" if warning else "")
        )
        if character.first_mes:
            for chunk in split_text(character.first_mes):
                await update.effective_message.reply_text(chunk)
            await self.service.mark_delivered(first_message_id)

    async def message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        try:
            reply = await self.service.converse(
                update.effective_user.id,
                update.effective_chat.id,
                f"{update.effective_chat.id}:{update.effective_message.message_id}",
                update.effective_message.text,
            )
            for chunk in split_text(reply.text):
                await update.effective_message.reply_text(chunk)
            await self.service.mark_delivered(reply.message_id)
        except NotReadyError as exc:
            await update.effective_message.reply_text(str(exc))
        except Exception:
            logger.exception("generation_failed")
            await update.effective_message.reply_text(
                "A geracao falhou e ficou registrada. Use /repetir para tentar de novo."
            )

    async def persona(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        raw = " ".join(context.args).strip()
        if raw:
            name, separator, description = raw.partition("|")
            persona = await self.service.set_persona(
                update.effective_user.id, name, description if separator else None
            )
            await update.effective_message.reply_text(f"Persona atualizada: {persona.name}")
        else:
            persona = await self.service.set_persona(update.effective_user.id)
            await update.effective_message.reply_text(
                f"Persona: {persona.name}\n{persona.description or '(sem descricao)'}\n\n"
                "Para editar: /persona Nome | descricao"
            )

    async def nova_conversa(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        await self.service.new_conversation(update.effective_user.id, update.effective_chat.id)
        await update.effective_message.reply_text(
            "Nova conversa iniciada. A relacao e as memorias foram preservadas."
        )

    async def memorias(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        ctx, memories = await self.service.list_memories(update.effective_user.id, update.effective_chat.id)
        listing = (
            "\n".join(f"{item.id} | {item.kind.value} | {item.content}" for item in memories)
            or "Nenhuma memoria vigente."
        )
        for chunk in split_text(listing):
            await update.effective_message.reply_text(chunk)
        base = (
            self.settings.data_dir / "vaults" / str(ctx.character.id) / "relationships" / str(ctx.persona.id)
        )
        for name in ("usuario.md", "relacionamento.md", "sonhos.md"):
            path = base / name
            if path.exists():
                await update.effective_message.reply_document(path)

    async def lembrar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        if len(context.args) < 2 or context.args[0] not in {"usuario", "relacao"}:
            await update.effective_message.reply_text("Uso: /lembrar usuario|relacao <texto>")
            return
        kind = MemoryKind.USER if context.args[0] == "usuario" else MemoryKind.RELATIONSHIP
        memory_id = await self.service.remember_manual(
            update.effective_user.id,
            update.effective_chat.id,
            kind,
            " ".join(context.args[1:]),
        )
        await update.effective_message.reply_text(f"Memoria registrada: {memory_id}")

    async def esquecer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        try:
            memory_id = uuid.UUID(context.args[0])
        except (IndexError, ValueError):
            await update.effective_message.reply_text("Uso: /esquecer <uuid>")
            return
        forgotten = await self.service.forget(update.effective_user.id, update.effective_chat.id, memory_id)
        await update.effective_message.reply_text(
            "Memoria esquecida; o historico foi preservado." if forgotten else "Memoria ativa nao encontrada."
        )

    async def exportar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        character, original, normalized = await self.service.export_character(
            update.effective_user.id, update.effective_chat.id
        )
        await update.effective_message.reply_document(
            io.BytesIO(original), filename=character.original_file_name, caption="Arquivo original"
        )
        await update.effective_message.reply_document(
            io.BytesIO(normalized), filename=f"{character.name}-normalized.json"
        )

    async def sonhar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        async with self.sessions.begin() as session:
            ctx = await self.service._context(session, update.effective_user.id, update.effective_chat.id)
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"dream:{ctx.relationship.id}"},
            )
            run = await self.dreams.run_relationship(session, ctx.relationship, force=True)
        await update.effective_message.reply_text(
            run.summary if run and run.summary else "Nao havia mensagens novas para sonhar."
        )

    async def sonhos(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        runs = await self.service.recent_dreams(update.effective_user.id, update.effective_chat.id)
        content = (
            "\n\n".join(
                f"{run.created_at}: {run.status.value}\n{run.summary or run.error or 'sem mudancas'}"
                for run in runs
            )
            or "Nenhum sonho registrado."
        )
        await update.effective_message.reply_text(content[:TELEGRAM_TEXT_LIMIT])

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        async with self.sessions() as session:
            await session.execute(text("SELECT 1"))
            pending = await session.scalar(
                select(Relationship).where(Relationship.dream_due_at.is_not(None)).limit(1)
            )
            latest = await session.scalar(select(DreamRun).order_by(DreamRun.created_at.desc()).limit(1))
        chat = self.settings.chat_profile
        dream = self.settings.dream_profile
        await update.effective_message.reply_text(
            "Banco: ok\n"
            f"Chat: {chat.model} (tools={chat.supports_tools})\n"
            f"Dream: {dream.model}\nDream pendente: {'sim' if pending else 'nao'}"
            f"\nUltimo dream: {latest.status.value if latest else 'nenhum'}"
        )

    async def repetir(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        try:
            reply = await self.service.retry_last(
                update.effective_user.id,
                update.effective_chat.id,
                f"retry:{update.effective_chat.id}:{update.effective_message.message_id}",
            )
            for chunk in split_text(reply.text):
                await update.effective_message.reply_text(chunk)
            await self.service.mark_delivered(reply.message_id)
        except NotReadyError as exc:
            await update.effective_message.reply_text(str(exc))

    async def ask_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        action = "conversation" if update.effective_message.text.startswith("/apagar_conversa") else "all"
        token = secrets.token_urlsafe(16)
        context.user_data[f"delete:{token}"] = {
            "action": action,
            "expires": datetime.now(UTC).timestamp() + 120,
        }
        label = "esta conversa" if action == "conversation" else "TODOS os dados"
        await update.effective_message.reply_text(
            f"Confirmar exclusao de {label}? O ledger removido nao pode ser recuperado sem backup.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Confirmar", callback_data=f"delete:{token}")]]
            ),
        )

    async def voz(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self.guard(update):
            return
        try:
            ctx = await self.service.active_context(update.effective_user.id, update.effective_chat.id)
        except NotReadyError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        if context.args:
            new_voice = " ".join(context.args).strip()
            await self.service.set_voice(update.effective_user.id, update.effective_chat.id, new_voice)
            await update.effective_message.reply_text(f"Voz alterada para: {new_voice}")
        else:
            current = ctx.character.voice_id or "(nenhuma)"
            await update.effective_message.reply_text(f"Voz atual: {current}\nPara trocar: /voz <id>")

    async def audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages and audio files."""
        if not await self.guard(update):
            return
        voice = update.effective_message.voice or update.effective_message.audio
        if not voice:
            return
        try:
            telegram_file = await voice.get_file()
            audio_bytes = bytes(await telegram_file.download_as_bytearray())
            if self.settings.chat_profile.supports_audio_input:
                reply = await self.service.converse_with_audio(
                    update.effective_user.id,
                    update.effective_chat.id,
                    f"{update.effective_chat.id}:{update.effective_message.message_id}",
                    audio_bytes,
                )
            else:
                # Fallback: treat audio as a normal message until transcription is implemented
                text_content = "(audio enviado pelo usuario — transcricao nao disponivel ainda)"
                reply = await self.service.converse(
                    update.effective_user.id,
                    update.effective_chat.id,
                    f"{update.effective_chat.id}:{update.effective_message.message_id}",
                    text_content,
                )
            for chunk in split_text(reply.text):
                await update.effective_message.reply_text(chunk)
            await self.service.mark_delivered(reply.message_id)
        except NotReadyError as exc:
            await update.effective_message.reply_text(str(exc))
        except Exception:
            logger.exception("audio_message_failed")
            await update.effective_message.reply_text("A geracao falhou. Use /repetir para tentar de novo.")

    async def confirm_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if not self.allowed(update):
            return
        data = context.user_data.pop(query.data, None)
        if not data or data["expires"] < datetime.now(UTC).timestamp():
            await query.edit_message_text("Confirmacao expirada.")
            return
        if data["action"] == "conversation":
            await self.service.delete_current_conversation(update.effective_user.id, update.effective_chat.id)
            await query.edit_message_text("Conversa apagada.")
        else:
            await self.service.delete_everything(update.effective_user.id)
            await query.edit_message_text("Todos os seus dados foram apagados.")

    def application(self) -> Application:
        app = Application.builder().token(self.settings.telegram_bot_token).build()
        handlers = {
            "start": self.start,
            "importar": self.importar,
            "exportar": self.exportar,
            "persona": self.persona,
            "nova_conversa": self.nova_conversa,
            "memorias": self.memorias,
            "lembrar": self.lembrar,
            "esquecer": self.esquecer,
            "sonhar": self.sonhar,
            "sonhos": self.sonhos,
            "status": self.status,
            "repetir": self.repetir,
            "apagar_conversa": self.ask_delete,
            "apagar_tudo": self.ask_delete,
            "voz": self.voz,
        }
        for name, callback in handlers.items():
            app.add_handler(CommandHandler(name, callback))
        app.add_handler(CallbackQueryHandler(self.confirm_delete, pattern=r"^delete:"))
        app.add_handler(MessageHandler(filters.PHOTO, self.photo))
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.audio))
        app.add_handler(MessageHandler(filters.Document.ALL, self.document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        # Schedule delivery polling
        app.job_queue.run_repeating(self._deliver_pending, interval=5, first=5)
        return app

    async def _deliver_pending(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Poll pending_deliveries and send media to the corresponding chat."""
        try:
            async with self.sessions.begin() as session:
                deliveries = list(
                    await session.scalars(
                        select(PendingDelivery)
                        .where(PendingDelivery.status == DeliveryStatus.PENDING)
                        .order_by(PendingDelivery.created_at)
                        .with_for_update(skip_locked=True)
                        .limit(5)
                    )
                )
                for delivery in deliveries:
                    try:
                        conversation = await session.get(Conversation, delivery.conversation_id)
                        if not conversation:
                            delivery.status = DeliveryStatus.FAILED
                            continue
                        chat_id = int(conversation.external_id)
                        if delivery.kind == DeliveryKind.IMAGE:
                            path = Path(delivery.content_path_or_text)
                            exists = await asyncio.to_thread(path.exists)
                            data = await asyncio.to_thread(path.read_bytes) if exists else None
                            if data:
                                await context.bot.send_photo(chat_id=chat_id, photo=data)
                            else:
                                delivery.status = DeliveryStatus.FAILED
                                continue
                        elif delivery.kind == DeliveryKind.AUDIO:
                            path = Path(delivery.content_path_or_text)
                            exists = await asyncio.to_thread(path.exists)
                            data = await asyncio.to_thread(path.read_bytes) if exists else None
                            if data:
                                await context.bot.send_voice(chat_id=chat_id, voice=data)
                            else:
                                delivery.status = DeliveryStatus.FAILED
                                continue
                        elif delivery.kind == DeliveryKind.TEXT:
                            for chunk in split_text(delivery.content_path_or_text):
                                await context.bot.send_message(chat_id=chat_id, text=chunk)
                        delivery.status = DeliveryStatus.DELIVERED
                    except Exception:
                        logger.exception("delivery_failed id=%s", delivery.id)
                        delivery.status = DeliveryStatus.FAILED
        except Exception:
            logger.exception("delivery_poll_error")


def main() -> None:
    settings = Settings.load()
    configure_logging(settings.log_level)
    TelegramAdapter(settings).application().run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
