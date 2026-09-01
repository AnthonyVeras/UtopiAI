from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from character_card import parse_character_card
from character_card.decoders import decode_payload
from character_card.png_chunks import find_text_value, scan_png_chunks

MAX_CARD_BYTES = 10 * 1024 * 1024
MAX_CARD_PAYLOAD_BYTES = 10 * 1024 * 1024
CARD_PARSE_TIMEOUT_SECONDS = 5


class CardError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedCard:
    name: str
    description: str
    personality: str
    scenario: str
    first_mes: str
    alternate_greetings: list[str]
    mes_example: str
    system_prompt: str
    post_history_instructions: str
    lorebook: dict[str, Any] | None
    payload: dict[str, Any]
    original_payload: dict[str, Any]
    original_format: str
    compatibility_warnings: list[str]


def _runtime_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def normalize_card(payload: dict[str, Any], original_format: str) -> NormalizedCard:
    data = _runtime_data(payload)
    name = str(data.get("name", "")).strip()
    if not name:
        raise CardError("O card nao possui um nome")
    lorebook = data.get("character_book") or data.get("lorebook")
    warnings: list[str] = []
    if isinstance(lorebook, dict):
        unsupported = {
            key
            for entry in lorebook.get("entries", [])
            if isinstance(entry, dict)
            for key in ("use_regex", "probability", "cooldown", "delay", "vectorized")
            if entry.get(key) not in (None, False, 0, 100)
        }
        if unsupported:
            warnings.append("Lorebook preservado, mas ignorando: " + ", ".join(sorted(unsupported)))
    normalized = {
        "name": name,
        "description": str(data.get("description", "")),
        "personality": str(data.get("personality", "")),
        "scenario": str(data.get("scenario", "")),
        "first_mes": str(data.get("first_mes", data.get("first_message", ""))),
        "alternate_greetings": list(data.get("alternate_greetings") or []),
        "mes_example": str(data.get("mes_example", "")),
        "system_prompt": str(data.get("system_prompt", "")),
        "post_history_instructions": str(data.get("post_history_instructions", "")),
        "character_book": lorebook,
    }
    return NormalizedCard(
        **{key: value for key, value in normalized.items() if key != "character_book"},
        lorebook=lorebook if isinstance(lorebook, dict) else None,
        payload=normalized,
        original_payload=payload,
        original_format=original_format,
        compatibility_warnings=warnings,
    )


def _parse_png_payload(blob: bytes) -> dict[str, Any]:
    parsed = parse_character_card(blob, ".png")
    chunks = scan_png_chunks(blob)
    raw = find_text_value(chunks, "ccv3") or find_text_value(chunks, "chara")
    payload = decode_payload(raw) if raw else None
    if payload is not None:
        return payload
    return {
        "name": parsed.name,
        "description": parsed.description,
        "personality": parsed.personality,
        "scenario": parsed.scenario,
        "first_mes": parsed.first_message,
        "alternate_greetings": parsed.alternate_greetings,
        "mes_example": parsed.mes_example,
        "system_prompt": parsed.system_prompt,
        "post_history_instructions": parsed.post_history_instructions,
        "character_book": parsed.character_book,
    }


def _parse_png_isolated(blob: bytes) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-m", "utopiai.cards", "--parse-png"],
            input=blob,
            capture_output=True,
            timeout=CARD_PARSE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CardError("O parsing do card PNG excedeu o limite de tempo") from exc
    except Exception as exc:
        raise CardError("Nao foi possivel iniciar o parser isolado do card PNG") from exc
    if result.returncode or not result.stdout or len(result.stdout) > MAX_CARD_PAYLOAD_BYTES:
        raise CardError("Card PNG invalido ou complexo demais")
    try:
        payload = json.loads(result.stdout)
    except Exception as exc:
        raise CardError("O parser do card PNG retornou um payload invalido") from exc
    if not isinstance(payload, dict):
        raise CardError("Payload do card nao e um objeto JSON")
    return payload


def load_card(blob: bytes, filename: str) -> NormalizedCard:
    if not blob or len(blob) > MAX_CARD_BYTES:
        raise CardError("O card deve ter entre 1 byte e 10 MB")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(blob)
        elif suffix == ".png":
            payload = _parse_png_isolated(blob)
        else:
            raise CardError("Envie um arquivo .json ou .png")
    except CardError:
        raise
    except Exception as exc:
        raise CardError(f"Card invalido: {exc}") from exc
    if not isinstance(payload, dict):
        raise CardError("Payload do card nao e um objeto JSON")
    return normalize_card(payload, suffix.removeprefix("."))


def _png_parser_main() -> int:
    try:
        blob = sys.stdin.buffer.read(MAX_CARD_BYTES + 1)
        if not blob or len(blob) > MAX_CARD_BYTES:
            raise CardError("Tamanho de card invalido")
        encoded = json.dumps(_parse_png_payload(blob), ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_CARD_PAYLOAD_BYTES:
            raise CardError("Payload de card acima do limite")
        sys.stdout.buffer.write(encoded)
        return 0
    except BaseException as exc:
        sys.stderr.write(type(exc).__name__)
        return 1


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return cleaned[:160] or "character-card.json"


def store_original(blob: bytes, filename: str, cards_dir: Path, character_id: str) -> Path:
    target_dir = cards_dir / character_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_filename(filename)
    fd, temporary_name = tempfile.mkstemp(dir=target_dir, prefix=".card-")
    try:
        with os.fdopen(fd, "wb") as temporary:
            temporary.write(blob)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return target


def normalized_json(card: NormalizedCard) -> bytes:
    return json.dumps(card.payload, ensure_ascii=False, indent=2).encode("utf-8")


if __name__ == "__main__" and "--parse-png" in sys.argv:
    raise SystemExit(_png_parser_main())
