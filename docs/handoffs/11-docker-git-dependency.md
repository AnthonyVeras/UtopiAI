# Handoff 11 — dependência Git na imagem Docker

- Objetivo: restaurar o build após fixar `character-card` em um commit Git.
- Alterações: estágio de build com Git, imagem final sem Git, build Docker no CI, runtime sem resync,
  imagem compartilhada e event loop de testes compatível com Psycopg no Windows.
- Migrações: nenhuma.
- Testes: build local, migração PostgreSQL, 25 testes (incluindo integração), Ruff e Compose.
- Limitações: o build ainda depende da disponibilidade do repositório Git fixado no lockfile.
- Próximo passo: configurar credenciais locais e executar smoke test de bot/worker.
