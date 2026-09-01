# Avaliação do MVP

`cases.jsonl` define 27 cenários. As categorias factuais/temporais são pontuadas por resposta
correta e ausência do fato rejeitado; personalidade, relação e naturalidade recebem nota humana de
1–5. Privacidade é binária: qualquer vazamento reprova o gate inteiro.

Registre uma execução em `docs/dogfooding/<data>-<modelo>.md` com commit, modelo, perfis, contagem de
acertos, falhas literais e mudanças propostas. Não ajuste o prompt usando casos secretos do mesmo
run; mantenha ao menos um conjunto de regressão estável.

