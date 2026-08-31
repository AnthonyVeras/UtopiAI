# ADR 0002 — Ledger PostgreSQL canônico

Status: aceito.

Decisão: memórias vivem em tabelas versionadas; Markdown é projeção atômica e reproduzível.

Motivo: arquivos são excelentes para inspeção/export, mas fracos para concorrência, evidência,
idempotência e exclusão relacional.

Consequência: toda escrita passa por transação e regenera o vault. Divergência do filesystem não
altera o prompt e pode ser reparada.

