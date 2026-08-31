# AGENTS.md

## Missão

Mantenha o UtopiAI como monólito modular orientado ao RP, não como lógica presa ao Telegram.
Código é em inglês; documentação e mensagens ao usuário são em português.

## Comandos obrigatórios

```bash
uv sync --dev
uv run ruff format .
uv run ruff check .
uv run pytest -q
docker compose config
```

Antes de deploy: `docker compose run --rm migrate` e smoke test de bot/worker.

## Fronteiras

- `telegram.py`: tradução de updates/comandos e entrega; nenhuma regra de memória.
- `service.py`: caso de uso de conversa e coordenação transacional.
- `cards.py` / `prompting.py`: entradas não confiáveis e composição de contexto.
- `memory.py` / `dreaming.py`: ledger, evidência, watermark e projeções.
- `llm.py`: única chamada direta ao LiteLLM.
- `models.py`: invariantes persistentes; mudanças exigem Alembic.

## Regras invioláveis

- Nunca injete `relationship_private` em grupos ou contextos diferentes da relação.
- Não dependa do modelo para esconder dado que já recebeu.
- Não apague memória para corrigir: use `superseded` ou `forgotten`.
- Não grave chaves, prompts completos ou conversas em logs.
- Preserve payload e arquivo original de cards; campos desconhecidos fazem round-trip.
- Toda proposta de dream precisa citar mensagens anteriores ao watermark.
- Resposta gerada deve existir no banco antes de ir ao canal.

## Escopo

Não adicione Redis, Celery, pgvector, FastAPI, painel, grupos, proatividade ou multimodal sem um
ADR, uma necessidade medida e aprovação explícita. Use Postgres, stdlib e os seams existentes.

## Git e handoff

Use branches curtas `feat/*`, `fix/*`, `docs/*` ou `test/*`; um assunto por PR; Conventional
Commits; squash merge para `main`. Atualize `CHANGELOG.md` e crie `docs/handoffs/<pr>.md` com:
objetivo, alterações, migrações, testes, limitações e próximo passo. Nunca versione `.env`,
`config/llm_profiles.toml`, cards, vaults ou backups.

