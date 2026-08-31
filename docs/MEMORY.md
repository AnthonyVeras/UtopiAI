# Memória

## Ledger

`memory_items` é canônico. Cada item possui relação, tipo (`user` ou `relationship`), conteúdo,
status, escopo, origem, confiança, importância, vigência e possível antecessor. `memory_sources`
liga memórias às mensagens que as sustentam.

Estados:

- `active`: pode entrar no prompt;
- `superseded`: foi substituída, mas permanece auditável;
- `forgotten`: usuário invalidou sem apagar a trilha;
- `rejected`: proposta de dream não aplicável.

Escopos:

- `relationship_private`: padrão do DM, nunca cruza para grupo;
- `conversation`: somente o episódio de origem;
- `shareable`: apta a outro contexto explicitamente autorizado.

O MVP só conversa em DM e grava memória automática como privada. Os escopos futuros já existem
para que grupos possam filtrar antes de construir o prompt.

## Memória imediata

Quando o perfil suporta tools, o modelo recebe `lembrar(tipo, fato, substitui_id?)`. A aplicação
fixa escopo/origem/evidência, limita quatro chamadas por turno, normaliza whitespace e deduplica
conteúdo vigente. Sem tool calling, o chat continua e o dream recupera fatos depois.

## Dream

Uma relação vence seis horas após a última mensagem. O worker fixa o timestamp da última mensagem
como watermark, processa somente mensagens novas e exige IDs de evidência pertencentes ao lote.
O par `(relationship_id, watermark)` é único. Falha de schema/provider recebe até três tentativas;
depois volta à fila em 30 minutos. Às 03:00 no timezone configurado, o worker recupera runs presos.

`share_worthy` habilita uma chance de 20% de instrução de alusão no próximo retorno. O sinal só é
consumido quando a resposta é entregue; não produz mensagem proativa.

## Markdown

Após mutações, três arquivos são substituídos atomicamente em
`vaults/{character}/relationships/{persona}`. `usuario.md` e `relacionamento.md` separam vigente e
histórico; `sonhos.md` lista consolidações. O prompt usa o ledger e o mesmo modelo semântico, não o
filesystem.

