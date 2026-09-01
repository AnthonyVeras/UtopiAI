import io
import json
import subprocess

import pytest
from character_card import embed_card_in_png
from PIL import Image

from utopiai.cards import CardError, load_card


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "V1", "description": "d", "personality": "p", "first_mes": "oi"},
        {
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": {"name": "V2", "description": "d", "personality": "p", "first_mes": "oi"},
        },
        {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                "name": "V3",
                "description": "d",
                "personality": "p",
                "first_mes": "oi",
                "future_field": {"preserve": True},
            },
        },
    ],
)
def test_loads_json_versions_and_preserves_unknown_fields(payload):
    card = load_card(json.dumps(payload).encode(), "card.json")
    assert card.name in {"V1", "V2", "V3"}
    assert card.original_payload == payload
    assert "creator_notes" not in card.payload


def test_loads_png_ccv3():
    image = io.BytesIO()
    Image.new("RGB", (4, 4), "purple").save(image, format="PNG")
    payload = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "Nyx",
            "description": "guardia",
            "personality": "calma",
            "first_mes": "Ola",
            "extensions": {"unknown": 42},
        },
    }
    png = embed_card_in_png(image.getvalue(), payload)
    card = load_card(png, "nyx.png")
    assert card.name == "Nyx"
    assert card.original_payload["data"]["extensions"]["unknown"] == 42


def test_rejects_bad_extension_and_size():
    with pytest.raises(CardError):
        load_card(b"{}", "card.txt")
    with pytest.raises(CardError):
        load_card(b"x" * (10 * 1024 * 1024 + 1), "card.json")


def test_rejects_truncated_png_as_card_error():
    truncated = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x20tEXtbroken"
    with pytest.raises(CardError, match="Card PNG invalido"):
        load_card(truncated, "broken.png")


def test_checks_size_before_starting_png_parser(monkeypatch):
    def parser_must_not_run(*args, **kwargs):
        pytest.fail("parser executado antes da verificacao de tamanho")

    monkeypatch.setattr("utopiai.cards.subprocess.run", parser_must_not_run)
    with pytest.raises(CardError, match="entre 1 byte e 10 MB"):
        load_card(b"x" * (10 * 1024 * 1024 + 1), "oversized.png")


def test_converts_png_parser_timeout_to_card_error(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 5)

    monkeypatch.setattr("utopiai.cards.subprocess.run", timeout)
    with pytest.raises(CardError, match="excedeu o limite de tempo"):
        load_card(b"\x89PNG\r\n\x1a\n", "slow.png")
