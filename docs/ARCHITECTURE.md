# Arquitetura

## Forma

```text
Telegram update
  -> TelegramAdapter
  -> ConversationService (transação + lock por conversa)
     -> Character Card adapter
     -> Prompt builder
     -> Memory ledger (PostgreSQL -> projeção Markdown)
     -> LiteLLM SDK -> provider

DreamWorker
  -> relação vencida (SKIP LOCKED + advisory lock)
  -> plano JSON do modelo dream
  -> validação de evidência
  -> ledger + dream_runs + projeções
```

É um único pacote e uma única imagem com entrypoints `utopiai-bot`, `utopiai-worker` e Alembic.
Bot e worker escalam como processos separados, sem separar deploys ou contratos de rede.

## Fluxo de mensagem

1. O adapter recusa usuários fora da allowlist e chats não privados.
2. O serviço obtém `user`, persona, personagem, relação e conversa.
3. `pg_advisory_xact_lock` serializa a conversa; `(channel, external_id)` deduplica redelivery.
4. A mensagem do usuário é gravada e o dream é agendado para seis horas depois.
5. O prompt usa card normalizado, lore ativo, persona, memórias vigentes e histórico recente.
6. LiteLLM responde; até quatro tool calls `lembrar` são validados pela aplicação.
7. A resposta é gravada como `generated`, enviada em blocos e marcada `delivered`.

## Dependências

O domínio usa SQLAlchemy diretamente: não há repositórios genéricos com uma única implementação.
`character-card` fica isolado em `cards.py`; LiteLLM fica isolado em `llm.py`. Isso é suficiente
para trocar canal ou biblioteca sem inventar interfaces antecipadas.

## Escalabilidade

Locks e restrições do PostgreSQL permitem múltiplos bots/workers. A etapa cara é o provider e não
há estado de conversa apenas em memória. Redis/fila externa entra somente se polling do banco ou
throughput medido não atender. Busca vetorial entra somente quando o benchmark mostrar queda por
volume de memória.

