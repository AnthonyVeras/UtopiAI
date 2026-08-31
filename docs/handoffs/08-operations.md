# Handoff 08 — operations

- Objetivo: deploy e recuperação reproduzíveis.
- Alterações: Compose, imagem 3.13, healthchecks, backup, logs e runbook.
- Migrações: serviço `migrate` antes de bot/worker.
- Testes: `docker compose config`; smoke ficou bloqueado pelo daemon local desligado.
- Limitações: backup local; primeiro start define o horário do ciclo diário.
- Próximo passo: avaliação e dogfooding.

