# Sistemas de memória e avaliação

## Hermes Agent

A separação entre identidade/agente, usuário e memórias inspirou arquivos legíveis e responsabilidades
distintas. O UtopiAI não copia arquivos como fonte canônica: usa ledger relacional e deriva Markdown.
Fonte: [Which file does what](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/which-file-does-what.md).

## OpenClaw

O modelo de memória curta, reflexão, promoção e proveniência é o análogo mais próximo de `sonhar`.
Foram reaproveitados watermark, consolidação explícita e trilha de origem; o worker não bloqueia a
conversa. Fonte: [OpenClaw memory](https://github.com/openclaw/openclaw/blob/main/docs/cli/memory.md).

## MemGPT / Letta

A distinção entre contexto ativo e armazenamento durável reforça que “janela maior” não é memória.
No MVP, uma projeção compacta ocupa contexto e o log completo permanece fora dele. Paginação e
busca vetorial só entram se volume real exigir.

## LongMemEval

A suíte local cobre as capacidades centrais de extração, raciocínio entre sessões, atualização,
temporalidade e abstenção, adicionando voz, relação, personas e privacidade. Fonte:
[LongMemEval](https://github.com/xiaowu0162/longmemeval).

`evals/cases.jsonl` contém 27 cenários. Resultados com modelo real devem registrar modelo, versão do
prompt, data, acerto factual/temporal e notas humanas. O mínimo é 90% factual/temporal e zero
vazamentos; uma média agregada nunca pode esconder falha de privacidade.

