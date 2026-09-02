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
    """Build a fake httpx response for mocking."""
    body = {
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "image", "data": image_b64}],
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

    async def mock_post(self, url, **kwargs):
        return _fake_response()

    with patch("httpx.AsyncClient.post", mock_post):
        path = await gw.generate_image(cid, jid, "a portrait")

    assert path.exists()
    assert path.suffix == ".png"
    assert str(cid) in str(path)


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

    # Should have 2 input parts: text + image
    assert len(captured_body["input"]) == 2
    assert captured_body["input"][1]["type"] == "image"


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

    assert len(captured_body["input"]) == 1  # only text, no image


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


def test_extract_image_missing():
    with pytest.raises(MediaError, match="nao contem imagem"):
        _extract_image({"steps": [{"type": "model_output", "content": []}]})


def test_extract_image_output_image_fallback():
    data = {"steps": [], "output_image": {"data": "abc123"}}
    assert _extract_image(data) == "abc123"


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
