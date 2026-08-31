# UtopiAI

UtopiAI é uma plataforma pessoal de personagens para RP, com memória de longo prazo auditável e
portabilidade por Character Cards. Telegram é o primeiro adaptador; o núcleo de personagem,
prompt, memória e LLM não depende dele.

## Executar localmente

Requisitos: Docker com Compose e Git. O runtime oficial é Python 3.13.

```bash
cp .env.example .env
cp config/llm_profiles.example.toml config/llm_profiles.toml
# edite os dois arquivos, sem commitar segredos
docker compose up --build
```

No Telegram, use `/importar` e envie um Character Card `.json` ou `.png`. Depois converse
normalmente. Somente IDs em `TELEGRAM_ALLOWED_USER_IDS` são atendidos e somente em chat privado.

## Desenvolvimento

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

As migrações são aplicadas pelo serviço `migrate`. Consulte [PROJECT.md](PROJECT.md),
[a arquitetura](docs/ARCHITECTURE.md) e [operações](docs/OPERATIONS.md) antes de alterar o fluxo.

## Estado do v0.1

O caminho funcional do MVP está implementado. O gate determinístico é automatizado; o gate de
dogfooding de sete dias depende de credenciais reais e uso humano. O projeto permanece privado e
sem licença pública até a decisão de abertura.

