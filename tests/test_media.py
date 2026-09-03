"""Tests for MediaGateway, media worker, card avatar extraction, delivery, and tool guards."""

import base64
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from utopiai.cards import load_card
from utopiai.config import LLMProfile
from utopiai.media import MediaError, MediaGateway, _extract_image

# --- MediaGateway ---


def _image_profile(*, supports_ref: bool = True) -> LLMProfile:
    return LLMProfile(
        model="gemini-test",
        api_key_env="GOOGLE_AI_STUDIO_API_KEY",
        timeout_seconds=10,
        provider="google-ai-studio",
        supports_reference_image=supports_ref,
    )


def _fake_response(status: int = 200, image_b64: str = "iVBORw0KGgo="):
    """Build a fake httpx response matching Google generateContent format."""
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": image_b64,
                            }
                        }
                    ]
                }
            }
        ]
    }
    resp = SimpleNamespace(
        status_code=status,
        text=json.dumps(body),
        json=lambda: body,
    )
    return resp


@pytest.mark.asyncio
async def test_generate_image_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "test-key")
    gw = MediaGateway(_image_profile(), tmp_path)
    cid = uuid.uuid4()
    jid = uuid.uuid4()
    captured_url = []
    captured_headers = {}

    async def mock_post(self, url, **kwargs):
        captured_url.append(str(url))
        captured_headers.update(kwargs.get("headers", {}))
        return _fake_response()

    with patch("httpx.AsyncClient.post", mock_post):
        path = await gw.generate_image(cid, jid, "a portrait")

    assert path.exists()
    assert path.suffix == ".png"
    assert str(cid) in str(path)
    assert captured_url[0].endswith("/v1beta/models/gemini-test:generateContent")
    assert captured_headers.get("x-goog-api-key") == "test-key"


@pytest.mark.asyncio
async def test_generate_image_with_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "test-key")
    gw = MediaGateway(_image_profile(supports_ref=True), tmp_path)
    # Create a fake avatar file
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    captured_body = {}

    async def mock_post(self, url, **kwargs):
        captured_body.update(kwargs.get("json", {}))
        return _fake_response()

    with patch("httpx.AsyncClient.post", mock_post):
        await gw.generate_image(uuid.uuid4(), uuid.uuid4(), "test", str(avatar))

    # Should have contents[0].parts: text + inline_data
    parts = captured_body["contents"][0]["parts"]
    assert len(parts) == 2
    assert parts[0]["text"] == "test"
    assert "inline_data" in parts[1]
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert captured_body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]


@pytest.mark.asyncio
async def test_generate_image_ignores_ref_when_unsupported(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "test-key")
    gw = MediaGateway(_image_profile(supports_ref=False), tmp_path)
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"\x89PNG\r\n\x1a\n")

    captured_body = {}

    async def mock_post(self, url, **kwargs):
        captured_body.update(kwargs.get("json", {}))
        return _fake_response()

    with patch("httpx.AsyncClient.post", mock_post):
        await gw.generate_image(uuid.uuid4(), uuid.uuid4(), "test", str(avatar))

    parts = captured_body["contents"][0]["parts"]
    assert len(parts) == 1  # only text, no inline_data
    assert parts[0]["text"] == "test"
    assert captured_body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]


@pytest.mark.asyncio
async def test_generate_image_api_error(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_AI_STUDIO_API_KEY", "test-key")
    gw = MediaGateway(_image_profile(), tmp_path)

    async def mock_post(self, url, **kwargs):
        return SimpleNamespace(status_code=500, text="server error")

    with patch("httpx.AsyncClient.post", mock_post):
        with pytest.raises(MediaError, match="HTTP 500"):
            await gw.generate_image(uuid.uuid4(), uuid.uuid4(), "test")


@pytest.mark.asyncio
async def test_generate_image_no_profile(tmp_path):
    gw = MediaGateway(None, tmp_path)
    with pytest.raises(MediaError, match="nao configurado"):
        await gw.generate_image(uuid.uuid4(), uuid.uuid4(), "test")


def test_extract_image_safety_blocked():
    data = {
        "promptFeedback": {"blockReason": "SAFETY"},
        "candidates": [],
    }
    with pytest.raises(MediaError, match="Prompt bloqueado por seguranca"):
        _extract_image(data)


def test_extract_image_finish_reason_safety():
    data = {
        "candidates": [
            {
                "finishReason": "SAFETY",
                "content": {"parts": []},
            }
        ]
    }
    with pytest.raises(MediaError, match="Geracao interrompida"):
        _extract_image(data)


# --- MediaWorker failure notification ---


@pytest.mark.asyncio
async def test_media_worker_failure_enqueues_text_notification(tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from utopiai.media_worker import MediaWorker
    from utopiai.models import (
        Base,
        Character,
        Conversation,
        DeliveryKind,
        MediaJob,
        MediaJobKind,
        MediaJobStatus,
        PendingDelivery,
        Persona,
        Relationship,
        User,
    )

    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory.begin() as session:
        user_id = uuid.uuid4()
        user = User(id=user_id)
        session.add(user)
        persona = Persona(id=uuid.uuid4(), user_id=user_id, name="User")
        session.add(persona)
        character = Character(
            id=uuid.uuid4(),
            owner_id=user_id,
            name="Luna",
            description="amiga",
            personality="calma",
            scenario="",
            first_mes="oi",
            normalized_card={},
            original_payload={},
            original_format="json",
            original_file_name="card.json",
            original_asset_path="card.json",
        )
        session.add(character)
        relationship = Relationship(character_id=character.id, persona_id=persona.id)
        session.add(relationship)
        conversation = Conversation(
            character_id=character.id,
            persona_id=persona.id,
            channel="telegram",
            external_id="100",
        )
        session.add(conversation)
        await session.flush()

        job = MediaJob(
            conversation_id=conversation.id,
            character_id=character.id,
            relationship_id=relationship.id,
            kind=MediaJobKind.IMAGE,
            prompt_or_text="retrato",
        )
        session.add(job)

    gw = MediaGateway(None, tmp_path)

    async def failing_generate_image(*args, **kwargs):
        raise MediaError("Google AI Studio HTTP 500: internal error")

    gw.generate_image = failing_generate_image
    worker = MediaWorker(SimpleNamespace(), factory, gw)
    did_work = await worker.run_one_pending()
    assert did_work is True

    async with factory() as session:
        from sqlalchemy import select

        jobs = (await session.scalars(select(MediaJob))).all()
        assert len(jobs) == 1
        assert jobs[0].status == MediaJobStatus.FAILED
        assert "Google AI Studio HTTP 500" in (jobs[0].error or "")

        deliveries = (await session.scalars(select(PendingDelivery))).all()
        assert len(deliveries) == 1
        assert deliveries[0].kind == DeliveryKind.TEXT
        assert "Nao consegui gerar a imagem agora" in deliveries[0].content_path_or_text

    await engine.dispose()



def test_extract_image_inline_data_snake_case():
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "here is your image"},
                        {"inline_data": {"mime_type": "image/png", "data": "snake_case_b64"}},
                    ]
                }
            }
        ]
    }
    assert _extract_image(data) == "snake_case_b64"


def test_extract_image_inline_data_camel_case():
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"inlineData": {"mimeType": "image/png", "data": "camelCase_b64"}},
                    ]
                }
            }
        ]
    }
    assert _extract_image(data) == "camelCase_b64"


# --- Card avatar extraction ---


def test_png_card_extracts_avatar():
    """PNG card should have avatar_data = the entire PNG blob."""
    import io

    from character_card import embed_card_in_png
    from PIL import Image

    image = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(image, format="PNG")
    payload = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {"name": "Test", "description": "d", "personality": "p", "first_mes": "hi"},
    }
    png = embed_card_in_png(image.getvalue(), payload)
    card = load_card(png, "test.png")
    assert card.avatar_data is not None
    assert card.avatar_data == png  # the PNG itself is the avatar


def test_json_card_with_avatar():
    avatar_bytes = b"\x89PNG\r\n\x1a\nfake"
    avatar_b64 = base64.b64encode(avatar_bytes).decode()
    payload = {
        "data": {
            "name": "JsonAvatar",
            "description": "d",
            "personality": "p",
            "first_mes": "hi",
            "avatar": f"data:image/png;base64,{avatar_b64}",
        }
    }
    card = load_card(json.dumps(payload).encode(), "card.json")
    assert card.avatar_data == avatar_bytes


def test_json_card_without_avatar():
    payload = {"name": "NoAvatar", "description": "d", "personality": "p", "first_mes": "hi"}
    card = load_card(json.dumps(payload).encode(), "card.json")
    assert card.avatar_data is None


# --- Tool availability guard ---


def test_enviar_imagem_not_exposed_without_avatar():
    """_available_tools should not include enviar_imagem when character has no avatar."""
    from utopiai.service import ConversationService, RuntimeContext

    char = SimpleNamespace(avatar_path=None, voice_id=None)
    ctx = RuntimeContext(
        user=SimpleNamespace(),
        persona=SimpleNamespace(),
        character=char,
        relationship=SimpleNamespace(),
        conversation=SimpleNamespace(),
    )
    settings = SimpleNamespace(
        chat_profile=SimpleNamespace(supports_tools=True),
        image_profile=_image_profile(),
        tts_profile=None,
    )
    svc = ConversationService.__new__(ConversationService)
    svc.settings = settings
    tools = svc._available_tools(ctx)
    tool_names = {t["function"]["name"] for t in tools}
    assert "enviar_imagem" not in tool_names
    assert "lembrar" in tool_names


def test_enviar_imagem_exposed_with_avatar():
    from utopiai.service import ConversationService, RuntimeContext

    char = SimpleNamespace(avatar_path="/some/avatar.png", voice_id=None)
    ctx = RuntimeContext(
        user=SimpleNamespace(),
        persona=SimpleNamespace(),
        character=char,
        relationship=SimpleNamespace(),
        conversation=SimpleNamespace(),
    )
    settings = SimpleNamespace(
        chat_profile=SimpleNamespace(supports_tools=True),
        image_profile=_image_profile(),
        tts_profile=None,
    )
    svc = ConversationService.__new__(ConversationService)
    svc.settings = settings
    tools = svc._available_tools(ctx)
    tool_names = {t["function"]["name"] for t in tools}
    assert "enviar_imagem" in tool_names


def test_enviar_audio_not_exposed_without_tts_profile():
    from utopiai.service import ConversationService, RuntimeContext

    char = SimpleNamespace(avatar_path="/a.png", voice_id="Kore")
    ctx = RuntimeContext(
        user=SimpleNamespace(),
        persona=SimpleNamespace(),
        character=char,
        relationship=SimpleNamespace(),
        conversation=SimpleNamespace(),
    )
    settings = SimpleNamespace(
        chat_profile=SimpleNamespace(supports_tools=True),
        image_profile=_image_profile(),
        tts_profile=None,  # no TTS profile
    )
    svc = ConversationService.__new__(ConversationService)
    svc.settings = settings
    tools = svc._available_tools(ctx)
    tool_names = {t["function"]["name"] for t in tools}
    assert "enviar_audio" not in tool_names


# --- suggest_voice stub ---


def test_suggest_voice_returns_default(tmp_path):
    gw = MediaGateway(None, tmp_path)
    assert gw.suggest_voice("shy and introverted") == "Kore"
