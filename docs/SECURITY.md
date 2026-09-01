# Segurança

## Modelo de ameaça do MVP

O deploy é pessoal e fechado, mas recebe dois tipos de entrada não confiável: updates Telegram e
Character Cards. A allowlist é aplicada antes de qualquer caso de uso e chats que não sejam DM são
recusados. Cards não controlam regras, permissões, ferramentas ou logs.

## Segredos e logs

Tokens e chaves vivem apenas no `.env`; os perfis TOML referenciam nomes de variáveis. Ambos os
arquivos locais são ignorados conforme necessário. `/status` mostra modelo/capacidade, nunca chave
ou base de prompt. Logs JSON contêm eventos, latência e tipos de erro; não devem receber conteúdo
integral de mensagens, prompts ou cards.

## Dados e exclusão

`/apagar_conversa` e `/apagar_tudo` exigem confirmação com token aleatório válido por dois minutos.
A exclusão do banco usa cascatas; assets são removidos somente após validar que o caminho resolvido
está dentro dos diretórios de dados. Backups podem reter dados por até sete dias e precisam ser
apagados separadamente para uma eliminação imediata completa.

## Riscos conhecidos

- Provider recebe o prompt necessário à geração e fica sujeito à sua política de dados.
- O backup local não protege contra perda total da VPS.
- Conteúdo 18+ depende das políticas e controles do provider escolhido.
- Markdown é exportável e deve herdar as permissões do volume/host.
- O estado temporário da confirmação de exclusão vive no processo do bot e some após restart.

## Dependências de baixa maturidade

`character-card` é fixada no commit
`8ec6a90140f1df6a4b8edbc5e78e2305841e1978`. A biblioteca tem poucos commits e mantenedor único;
portanto, nunca deve ser atualizada automaticamente. Antes de cada atualização, revise manualmente
o diff, em especial `png_chunks.py`, `decoders.py` e os parsers, execute todos os fixtures e fixe o
novo hash somente depois da aprovação.

Na revisão de 2026-09-01, `png_chunks.py` mostrou parsing linear e slices limitados pela entrada,
mas não valida CRC e usa descompressão zlib sem limite de saída. Por isso, o UtopiAI rejeita cards
acima de 10 MB antes de decodificar e processa PNG em subprocesso descartável, com timeout de cinco
segundos e payload serializado limitado a 10 MB. Falha, timeout ou término anormal do subprocesso
vira `CardError` e não encerra o bot.

Antes de beta multiusuário: criptografia/segregação de backup, política de retenção, backup externo,
revisão LGPD, rate limit e testes de autorização negativos.
