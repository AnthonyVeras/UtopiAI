# Prompting

## Ordem

1. contrato do núcleo e privacidade;
2. `system_prompt` do card, subordinado ao núcleo;
3. lore antes da definição;
4. descrição, personalidade e cenário;
5. persona;
6. memórias vigentes do usuário e da relação;
7. lore posterior e exemplos;
8. histórico recente;
9. instruções pós-histórico;
10. mensagem atual e ferramenta de memória.

Macros: `{{char}}`, `{{user}}`, `{{description}}`, `{{personality}}`, `{{scenario}}`. Macros
desconhecidas permanecem literais. `creator_notes`, tags e metadados não entram no prompt.

## Orçamento

O MVP usa uma estimativa conservadora de quatro caracteres por token. Reserva saída e seções do
sistema; o histórico ocupa o restante, do mais recente ao mais antigo. Lore tem orçamento próprio
de 1.500 tokens estimados. Um tokenizer específico será adicionado apenas se as avaliações
detectarem truncamento ruim em modelos reais.

## Segurança

Cards são entrada não confiável. Suas instruções aparecem depois do contrato do núcleo e não têm
permissão para mudar privacidade, tools ou logs. Conteúdo privado não autorizado é removido antes
da chamada ao modelo — uma instrução de “não vazar” nunca substitui essa filtragem.

