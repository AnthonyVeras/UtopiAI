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
