# Handoff 10 — hardening de Character Cards

- Objetivo: impedir atualização não revisada da dependência e conter PNGs malformados.
- Alterações: commit Git fixo, parser PNG isolado, timeout de cinco segundos e limite de payload.
- Migrações: nenhuma.
- Testes: PNG truncado, limite antes do parser, timeout, suíte completa, Ruff e Compose.
- Limitações: a dependência continua de baixa maturidade e exige revisão manual em cada atualização.
- Próximo passo: antes de beta público, fuzzing de PNG e limites de recursos do container.
