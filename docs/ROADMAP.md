# Roadmap

## Gate v0.1

Primeiro: testes determinísticos, benchmark com 27 casos e dogfooding de sete dias/100 turnos/três
dreams. Nenhuma feature seguinte entra se houver perda de dados, identidade inconsistente,
supersede errado ou vazamento de escopo nos últimos 50 turnos.

## v1.5 — multimodal e ajuste

Entrada: gate v0.1 aprovado e custo/latência conhecidos. Saída: envio/recebimento de imagem e áudio,
armazenamento com retenção explícita e controles de geração seguros. Temperatura e limites podem
ser expostos sem revelar segredos do provider.

## v1.5/v2 — relacionamento estruturado

Entrada: avaliações mostrarem que texto livre não produz evolução consistente. Definir dimensões
observáveis (confiança, afeição etc.), regras de atualização auditáveis e testes contra manipulação.

## v2 — iniciativa

Entrada: política de horário, opt-in, frequência e cancelamento. Mensagens proativas usam outbox
idempotente; dream pode sugerir, mas nunca enviar diretamente.

## v2 — grupos e plataformas

Entrada: suíte de privacidade com zero vazamentos. O prompt de grupo recebe somente memórias
`shareable` e `conversation` do grupo. Turn-taking terá orçamento, máximo de rodadas e ação humana
para impedir loops. Discord, WhatsApp e web serão adapters do mesmo serviço.

## v3 — rede social de personagens

Só após identidade, consentimento, proveniência e moderação entre bots estarem definidos. Relações
bot-bot não reutilizam silenciosamente memórias privadas bot-usuário.

Monetização, catálogo e licença open source dependem de estabilidade de schema, política de dados
e decisão explícita de licença.

