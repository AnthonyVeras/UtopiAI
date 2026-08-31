# Character Cards

## Compatibilidade

São aceitos JSON V1 plano, JSON V2/V3 com `data` e PNG com chunks `chara`/`ccv3`, até 10 MB. A
biblioteca `character-card` valida PNG; JSON é lido pela stdlib e normalizado pelo mesmo adapter.
O arquivo original e seu payload completo são preservados para export fiel.

Runtime: `name`, `description`, `personality`, `scenario`, `first_mes`, `alternate_greetings`,
`mes_example`, `system_prompt`, `post_history_instructions` e lorebook básico.

## Lorebook do MVP

Suporta entradas constantes, chaves primárias/secundárias, `enabled`, `case_sensitive`,
`selective`, prioridade, ordem e posição antes/depois. O scan usa as 12 mensagens recentes e a
mensagem atual. O orçamento é aplicado por prioridade.

Regex, recursão, probabilidade, cooldown, delay e vetores são preservados no original e geram aviso
quando detectados, mas não afetam o runtime.

## Importação

Um card válido arquiva o personagem anterior, cria relação para a persona ativa, conversa e vault.
As relações antigas continuam no banco e não são misturadas. `first_mes` é enviado pelo canal sem
ser reinterpretado.

