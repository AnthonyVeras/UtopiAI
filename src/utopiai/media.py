from __future__ import annotations

import base64
import logging
import os
import tempfile
import uuid
from pathlib import Path

import httpx

from utopiai.config import LLMProfile

logger = logging.getLogger(__name__)

GOOGLE_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
IMAGE_TIMEOUT = 90
DEFAULT_VOICE_ID = "Kore"  # ponytail: stub, replaced when TTS API details arrive


class MediaError(RuntimeError):
    pass


class MediaGateway:
    def __init__(self, image_profile: LLMProfile | None, data_dir: Path):
        self.image_profile = image_profile
        self.data_dir = data_dir

    async def generate_image(
        self,
        character_id: uuid.UUID,
        job_id: uuid.UUID,
        prompt: str,
        reference_image_path: str | None = None,
    ) -> Path:
        """Generate image via Google AI Studio generateContent endpoint.

        Uses responseModalities=["TEXT","IMAGE"] to request image output.
        Sends the avatar as inline_data when the profile supports it
        and a path is provided, enabling facial consistency.
        """
        profile = self.image_profile
        if not profile:
            raise MediaError("Perfil de imagem nao configurado")

        parts: list[dict] = [{"text": prompt}]
        if reference_image_path and profile.supports_reference_image:
            ref_data = await _read_image_b64(reference_image_path)
            suffix = Path(reference_image_path).suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            parts.append({"inline_data": {"mime_type": mime, "data": ref_data}})

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        url = GOOGLE_GENERATE_URL.format(model=profile.model)
        timeout = profile.timeout_seconds or IMAGE_TIMEOUT
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "x-goog-api-key": profile.api_key,
                    "Content-Type": "application/json",
                },
                json=body,
            )
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise MediaError(f"Google AI Studio HTTP {resp.status_code}: {detail}")

        image_data = _extract_image(resp.json())
        out = self._media_path(character_id, job_id, "png")
        out.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(out, base64.b64decode(image_data))
        return out

    async def synthesize_speech(
        self,
        character_id: uuid.UUID,
        job_id: uuid.UUID,
        text: str,
        voice_id: str,
    ) -> Path:
        # ponytail: stub until TTS API details arrive
        raise MediaError("TTS nao implementado ainda")

    async def transcribe_audio(self, audio_path: str) -> str:
        # ponytail: stub until TTS profile arrives
        raise MediaError("Transcricao nao implementada ainda")

    def suggest_voice(self, personality: str) -> str:
        # ponytail: returns default, upgrade when voice catalog available
        return DEFAULT_VOICE_ID

    def _media_path(self, character_id: uuid.UUID, job_id: uuid.UUID, ext: str) -> Path:
        return self.data_dir / "media" / str(character_id) / f"{job_id}.{ext}"


def _extract_image(data: dict) -> str:
    """Walk generateContent response to find the first image part.

    Response format: candidates[0].content.parts[] — look for a part
    with "inlineData" (or "inline_data") containing base64 image data.
    """
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            # Google uses camelCase in REST responses
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline["data"]
    raise MediaError("Resposta da API nao contem imagem")


async def _read_image_b64(path: str) -> str:
    """Read an image file and return base64-encoded content."""
    import asyncio

    raw = await asyncio.to_thread(Path(path).read_bytes)
    return base64.b64encode(raw).decode("ascii")


def _atomic_write(target: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".media-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
