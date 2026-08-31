# Handoff 02 — database core

- Objetivo: persistir pessoas, cards, conversas, mensagens, relações, memória, dreams e chamadas.
- Alterações: modelos SQLAlchemy, sessão assíncrona e baseline Alembic explícito.
- Migrações: `0001_initial_schema`.
- Testes: criação integral do metadata em SQLite; migration smoke depende de Docker/Postgres.
- Limitações: nenhum upgrade anterior ao baseline.
- Próximo passo: importar cards portáveis.

