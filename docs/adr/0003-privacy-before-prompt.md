# ADR 0003 — Privacidade antes do prompt

Status: aceito.

Decisão: escopo é aplicado pela consulta antes de chamar o modelo. Memória privada nunca é injetada
em grupo; o modelo pode receber somente a informação abstrata de que há limites.

Motivo: instruir um LLM a não revelar conteúdo que recebeu não é uma fronteira de segurança.

Consequência: grupos exigirão query/policy própria e testes de zero vazamento antes de lançamento.

