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

Antes de beta multiusuário: criptografia/segregação de backup, política de retenção, backup externo,
revisão LGPD, rate limit e testes de autorização negativos.

