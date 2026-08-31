# ADR 0006 — Python 3.13 para `character-card`

Status: aceito.

Decisão: o runtime mínimo foi atualizado de Python 3.12 para 3.13 por decisão do proprietário.

Motivo: a biblioteca `character-card` escolhida para V1–V3 exige Python 3.13. Manter 3.12 exigiria
trocar a dependência ou sustentar dois parsers.

Consequência: imagem, metadata e ambiente de desenvolvimento devem permanecer em 3.13+.

