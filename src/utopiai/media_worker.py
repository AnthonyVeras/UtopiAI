from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from utopiai.config import Settings
from utopiai.media import MediaGateway
from utopiai.models import (
    Character,
    DeliveryKind,
    MediaJob,
    MediaJobKind,
    MediaJobStatus,
    PendingDelivery,
    now_utc,
)

logger = logging.getLogger(__name__)


class MediaWorker:
    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker[AsyncSession],
        gateway: MediaGateway,
    ):
        self.settings = settings
        self.sessions = sessions
        self.gateway = gateway

    async def run_one_pending(self) -> bool:
        async with self.sessions.begin() as session:
            job = await session.scalar(
                select(MediaJob)
                .where(MediaJob.status == MediaJobStatus.PENDING)
                .order_by(MediaJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not job:
                return False
            job.status = MediaJobStatus.RUNNING
            await session.flush()
            try:
                result_path = await self._process(session, job)
                job.status = MediaJobStatus.DONE
                job.result_path = str(result_path)
                job.finished_at = now_utc()
                delivery_kind = DeliveryKind.IMAGE if job.kind == MediaJobKind.IMAGE else DeliveryKind.AUDIO
                session.add(
                    PendingDelivery(
                        conversation_id=job.conversation_id,
                        kind=delivery_kind,
                        content_path_or_text=str(result_path),
                    )
                )
            except Exception as exc:
                logger.exception("media_job_failed job=%s", job.id)
                job.status = MediaJobStatus.FAILED
                job.error = f"{type(exc).__name__}: {exc}"[:2000]
                job.finished_at = now_utc()
                failure_msg = (
                    "Nao consegui gerar a imagem agora. Tente novamente mais tarde."
                    if job.kind == MediaJobKind.IMAGE
                    else "Nao consegui gerar o audio agora. Tente novamente mais tarde."
                )
                session.add(
                    PendingDelivery(
                        conversation_id=job.conversation_id,
                        kind=DeliveryKind.TEXT,
                        content_path_or_text=failure_msg,
                    )
                )
            return True

    async def _process(self, session: AsyncSession, job: MediaJob) -> Path:
        character = await session.get(Character, job.character_id)
        if job.kind == MediaJobKind.IMAGE:
            return await self.gateway.generate_image(
                character_id=job.character_id,
                job_id=job.id,
                prompt=job.prompt_or_text,
                reference_image_path=character.avatar_path if character else None,
            )
        elif job.kind == MediaJobKind.AUDIO:
            voice = character.voice_id if character else None
            return await self.gateway.synthesize_speech(
                character_id=job.character_id,
                job_id=job.id,
                text=job.prompt_or_text,
                voice_id=voice or "Kore",
            )
        raise ValueError(f"Tipo de media_job desconhecido: {job.kind}")
