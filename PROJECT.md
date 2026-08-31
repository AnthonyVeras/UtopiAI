# UtopiAI — arquivo central do projeto

## Produto

UtopiAI cria relações contínuas com personagens portáveis. O valor não é “um chatbot com
histórico”, mas uma memória que o usuário consegue inspecionar, corrigir, invalidar e exportar.

## MVP v0.1

- proprietário único autorizado, conversa privada e texto;
- um personagem ativo, importado de Character Card JSON/PNG V1–V3;
- persona do usuário como fronteira de relação;
- histórico bruto no PostgreSQL;
- ledger versionado e projeções Markdown para Obsidian;
- memória imediata por `lembrar` e consolidação por `sonhar`;
- perfis LiteLLM independentes para chat e dream;
- Telegram via long polling e Docker Compose.

Não fazem parte deste corte: grupos, proatividade, multimodal, pensamentos expostos, pontos de
afeição, painel, catálogo e monetização.

## Glossário

- **Character Card:** identidade portátil do personagem; o original nunca é reescrito.
- **Persona:** identidade de RP do usuário. Trocar persona cria outra relação.
- **Relação:** vínculo estável de `personagem + persona`, atravessando conversas.
- **Conversa:** episódio com histórico próprio. `/nova_conversa` encerra somente o episódio.
- **Ledger:** fonte canônica e histórica das memórias no PostgreSQL.
- **Projeção:** visão Markdown reproduzível do ledger; não é fonte de escrita.
- **Dream:** consolidação assíncrona das mensagens desde um watermark.
- **Escopo:** limite de circulação de uma memória; conteúdo privado não chega a contexto coletivo.

## Invariantes

1. O banco é a fonte canônica; apagar ou editar Markdown não muda memória.
2. Memória privada não é entregue ao modelo em contexto que não a autoriza.
3. Supersede e forget nunca apagam a trilha histórica.
4. Uma execução de dream é única por relação e watermark.
5. Card e prompt do card não podem substituir regras do núcleo.
6. Resposta é persistida antes do envio e marcada entregue somente depois.
7. Segredos e conteúdo integral de conversas não aparecem em logs.

## Critério de conclusão

O gate técnico exige testes determinísticos verdes, ao menos 90% na avaliação factual/temporal,
zero vazamento de escopo, zero perda/duplicação no retry e overhead p95 abaixo de 500 ms sem o
fornecedor. O gate humano exige sete dias, 100 turnos, três dreams e média 4/5 em voz,
continuidade, iniciativa narrativa e naturalidade.

O roadmap detalhado está em [docs/ROADMAP.md](docs/ROADMAP.md).

