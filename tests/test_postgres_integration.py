import asyncio
import json
import os
from datetime import timedelta
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from utopiai.config import LLMProfile, Settings
from utopiai.dreaming import DreamWorker
from utopiai.llm import LLMResult
from utopiai.models import Base, DreamRun, Message, Relationship, now_utc
from utopiai.service import ConversationService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL nao configurada"
)


@pytest.fixture
async def postgres(tmp_path, monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setenv("TEST_CHAT_KEY", "test")
    monkeypatch.setenv("TEST_DREAM_KEY", "test")
    settings = Settings(
        database_url=url,
        telegram_bot_token="test",
        telegram_allowed_user_ids=frozenset({7}),
        data_dir=tmp_path,
        timezone="America/Sao_Paulo",
        log_level="INFO",
        chat_profile=LLMProfile(model="test/chat", api_key_env="TEST_CHAT_KEY"),
        dream_profile=LLMProfile(model="test/dream", api_key_env="TEST_DREAM_KEY"),
    )
    yield settings, factory
    await engine.dispose()


def card_blob() -> bytes:
    return json.dumps(
        {"name": "Luna", "description": "amiga", "personality": "calma", "first_mes": ""}
    ).encode()


async def fake_chat(*args, **kwargs):
    return LLMResult("Resposta unica", [], 20, 4, 0.001, 5)


async def test_redelivery_new_conversation_and_persistence(postgres, monkeypatch):
    settings, factory = postgres
    monkeypatch.setattr("utopiai.service.complete", fake_chat)
    service = ConversationService(settings, factory)
    await service.import_character(7, 70, "luna.json", card_blob())
    first = await service.converse(7, 70, "70:1", "Oi")
    duplicate = await service.converse(7, 70, "70:1", "Oi")
    assert duplicate.message_id == first.message_id
    assert duplicate.duplicate
    await service.mark_delivered(first.message_id)
    context = await service.active_context(7, 70)
    relationship_id = context.relationship.id
    await service.new_conversation(7, 70)
    next_context = await service.active_context(7, 70)
    assert next_context.conversation.id != context.conversation.id
    assert next_context.relationship.id == relationship_id
    async with factory() as session:
        assert await session.scalar(select(func.count(Message.id))) == 2


async def test_two_workers_do_not_duplicate_dream(postgres, monkeypatch):
    settings, factory = postgres
    monkeypatch.setattr("utopiai.service.complete", fake_chat)
    service = ConversationService(settings, factory)
    await service.import_character(7, 70, "luna.json", card_blob())
    reply = await service.converse(7, 70, "70:2", "Eu gosto de chuva")
    await service.mark_delivered(reply.message_id)
    async with factory.begin() as session:
        relationship = await session.scalar(select(Relationship))
        relationship.dream_due_at = now_utc() - timedelta(seconds=1)

    async def fake_dream(*args, **kwargs):
        plan = {
            "summary": "Nada novo",
            "share_worthy": False,
            "interestingness": 0,
            "changes": [{"operation": "noop"}],
        }
        return LLMResult(json.dumps(plan), [], 40, 10, 0.001, 5)

    monkeypatch.setattr("utopiai.dreaming.complete", fake_dream)
    workers = [DreamWorker(settings, factory), DreamWorker(settings, factory)]
    results = await asyncio.gather(*(worker.run_one_due() for worker in workers))
    assert sorted(results) == [False, True]
    async with factory() as session:
        assert await session.scalar(select(func.count(DreamRun.id))) == 1
