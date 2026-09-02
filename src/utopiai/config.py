from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMProfile:
    model: str
    api_key_env: str
    context_window: int = 32_768
    max_output_tokens: int = 1_200
    temperature: float = 0.8
    timeout_seconds: int = 90
    api_base: str | None = None
    provider: str | None = None
    supports_tools: bool | str = "auto"
    supports_vision: bool = False
    supports_audio_input: bool = False
    supports_reference_image: bool = False

    @property
    def api_key(self) -> str:
        value = os.getenv(self.api_key_env)
        if not value:
            raise RuntimeError(f"Variavel obrigatoria ausente: {self.api_key_env}")
        return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    telegram_bot_token: str
    telegram_allowed_user_ids: frozenset[int]
    data_dir: Path
    timezone: str
    log_level: str
    chat_profile: LLMProfile
    dream_profile: LLMProfile
    image_profile: LLMProfile | None = None
    tts_profile: LLMProfile | None = None

    @classmethod
    def load(cls) -> Settings:
        profile_path = Path(os.getenv("LLM_PROFILES_PATH", "config/llm_profiles.toml"))
        if not profile_path.exists():
            raise RuntimeError(
                f"Perfil LLM nao encontrado em {profile_path}. Copie config/llm_profiles.example.toml."
            )
        raw = tomllib.loads(profile_path.read_text(encoding="utf-8"))["profiles"]
        allowed = frozenset(
            int(value.strip())
            for value in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
            if value.strip()
        )
        if not allowed:
            raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS deve conter ao menos um ID")
        return cls(
            database_url=os.getenv(
                "DATABASE_URL", "postgresql+psycopg://utopiai:utopiai@localhost:5432/utopiai"
            ),
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_allowed_user_ids=allowed,
            data_dir=Path(os.getenv("DATA_DIR", ".")),
            timezone=os.getenv("TIMEZONE", "America/Sao_Paulo"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            chat_profile=LLMProfile(**raw["chat"]),
            dream_profile=LLMProfile(**raw["dream"]),
            image_profile=LLMProfile(**raw["image"]) if "image" in raw else None,
            tts_profile=LLMProfile(**raw["tts"]) if "tts" in raw else None,
        )
