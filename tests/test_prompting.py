from types import SimpleNamespace

from utopiai.models import MemoryKind
from utopiai.prompting import PromptInput, PromptMemory, active_lore, build_prompt, replace_macros


def character(**overrides):
    values = {
        "name": "Luna",
        "description": "amiga de {{user}}",
        "personality": "curiosa",
        "scenario": "biblioteca",
        "system_prompt": "Fale baixo.",
        "mes_example": "{{char}}: achei um livro",
        "post_history_instructions": "Continue como {{char}}.",
        "lorebook": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_macros_and_prompt_order_and_creator_notes_absence():
    messages = build_prompt(
        PromptInput(
            character=character(),
            persona_name="Alex",
            persona_description="gosta de astronomia",
            memories=[PromptMemory(MemoryKind.USER, "Alex prefere cha")],
            history=[("assistant", "Bem-vindo")],
            current_message="Oi, {{char}}",
        ),
        context_window=4096,
        max_output_tokens=500,
    )
    system = messages[0]["content"]
    assert system.index("regras do sistema") < system.index("Fale baixo")
    assert system.index("Personagem: Luna") < system.index("Persona do usuario")
    assert system.index("Persona do usuario") < system.index("Memoria sobre o usuario")
    assert "creator_notes" not in system
    assert messages[-1] == {"role": "user", "content": "Oi, Luna"}


def test_lore_activation_selective_case_order_and_budget():
    book = {
        "entries": [
            {"constant": True, "content": "constante", "priority": 1, "position": "before"},
            {"keys": ["Lua"], "content": "caso", "case_sensitive": True, "position": "after"},
            {
                "keys": ["porto"],
                "secondary_keys": ["chuva"],
                "selective": True,
                "content": "segredo",
                "priority": 9,
            },
            {"keys": ["porto"], "content": "muito longo para caber", "priority": 0},
        ]
    }
    before, after = active_lore(book, "No porto com chuva. Lua", token_budget=7)
    assert before[:2] == ["segredo", "constante"]
    assert after == ["caso"]
    assert active_lore(book, "lua", 20)[1] == []


def test_history_is_truncated_oldest_first():
    messages = build_prompt(
        PromptInput(
            character=character(system_prompt="", mes_example="", post_history_instructions=""),
            persona_name="Alex",
            persona_description="",
            memories=[],
            history=[("user", "antiga " * 100), ("assistant", "recente")],
            current_message="agora",
        ),
        context_window=250,
        max_output_tokens=40,
    )
    contents = [message["content"] for message in messages]
    assert "recente" in contents
    assert "antiga " * 100 not in contents


def test_replace_macros_leaves_unknown_macro():
    assert replace_macros("{{char}} {{unknown}}", {"char": "A"}) == "A {{unknown}}"
