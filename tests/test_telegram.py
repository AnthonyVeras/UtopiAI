from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from utopiai.telegram import CARD_PHOTO_HINT, TelegramAdapter, split_text


def test_split_text_preserves_content_within_limit():
    value = ("linha longa com palavras\n" * 500).strip()
    chunks = split_text(value, 120)
    assert all(0 < len(chunk) <= 120 for chunk in chunks)
    assert "".join(chunks).replace(" ", "").replace("\n", "") == value.replace(" ", "").replace("\n", "")


@pytest.mark.asyncio
async def test_photo_during_import_explains_document_upload_and_keeps_state():
    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.guard = AsyncMock(return_value=True)
    reply_text = AsyncMock()
    update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(user_data={"awaiting_card": True})

    await adapter.photo(update, context)

    reply_text.assert_awaited_once_with(CARD_PHOTO_HINT)
    assert context.user_data["awaiting_card"] is True


@pytest.mark.asyncio
async def test_photo_without_vision_support_warns_user():
    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.guard = AsyncMock(return_value=True)
    adapter.settings = SimpleNamespace(
        chat_profile=SimpleNamespace(supports_vision=False),
    )
    reply_text = AsyncMock()
    update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(user_data={})

    await adapter.photo(update, context)

    reply_text.assert_awaited_once_with("Este personagem nao possui visao habilitada no momento.")


def test_telegram_application_builds_with_job_queue():
    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.settings = SimpleNamespace(telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    app = adapter.application()
    assert app.job_queue is not None


@pytest.mark.asyncio
async def test_photo_size_limit():
    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.guard = AsyncMock(return_value=True)
    adapter.settings = SimpleNamespace(
        chat_profile=SimpleNamespace(supports_vision=True),
    )
    reply_text = AsyncMock()
    photo_item = SimpleNamespace(file_size=15 * 1024 * 1024)  # 15 MB
    update = SimpleNamespace(
        effective_message=SimpleNamespace(photo=[photo_item], reply_text=reply_text)
    )
    context = SimpleNamespace(user_data={})

    await adapter.photo(update, context)

    reply_text.assert_awaited_once_with("Arquivo acima do limite de 10 MB.")


@pytest.mark.asyncio
async def test_audio_size_limit():
    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.guard = AsyncMock(return_value=True)
    reply_text = AsyncMock()
    voice_item = SimpleNamespace(file_size=25 * 1024 * 1024)  # 25 MB
    update = SimpleNamespace(
        effective_message=SimpleNamespace(voice=voice_item, audio=None, reply_text=reply_text)
    )
    context = SimpleNamespace(user_data={})

    await adapter.audio(update, context)

    reply_text.assert_awaited_once_with("Arquivo de audio acima do limite de 20 MB.")


@pytest.mark.asyncio
async def test_sonhar_failed_reports_error():
    from utopiai.models import DreamStatus

    adapter = TelegramAdapter.__new__(TelegramAdapter)
    adapter.guard = AsyncMock(return_value=True)

    fake_run = SimpleNamespace(
        status=DreamStatus.FAILED,
        summary=None,
        error="Erro na API de dream",
    )

    adapter.service = SimpleNamespace(
        _context=AsyncMock(return_value=SimpleNamespace(relationship=SimpleNamespace(id=1))),
    )
    adapter.dreams = SimpleNamespace(
        run_relationship=AsyncMock(return_value=fake_run),
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, *args, **kwargs):
            pass

    adapter.sessions = SimpleNamespace(begin=lambda: FakeSession())

    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        effective_message=SimpleNamespace(reply_text=reply_text),
    )
    context = SimpleNamespace(user_data={})

    await adapter.sonhar(update, context)

    reply_text.assert_awaited_once_with("Falha ao processar o sonho: Erro na API de dream")

