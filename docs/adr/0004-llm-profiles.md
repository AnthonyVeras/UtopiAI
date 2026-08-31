# ADR 0004 — Perfis LLM por papel

Status: aceito.

Decisão: `chat` e `dream` têm configurações independentes em TOML e usam LiteLLM SDK direto.

Motivo: RP favorece escrita/interpretação; consolidação favorece JSON confiável e baixo custo. Um
proxy ou adapter por provider não agrega valor no MVP.

Consequência: o mesmo modelo pode preencher os dois papéis; recursos não suportados degradam sem
parar conversa. Segredos continuam em ambiente.

