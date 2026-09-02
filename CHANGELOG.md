# Changelog

Formato baseado em Keep a Changelog. O projeto ainda não possui licença pública.

## [Unreleased]

### Security

- Fixado `character-card` em um commit revisado, evitando atualização implícita de supply-chain.
- Isolado o parsing de PNG não confiável em subprocesso com timeout e limites de entrada/saída.

### Fixed

- Adicionado extra `[job-queue]` ao `python-telegram-bot` e explicitadas as dependências `httpx` e `pillow`.
- Corrigido endpoint do Google AI Studio para geração de imagem multimodal (`models/{model}:generateContent`).
- Adicionado feedback amigável ao usuário caso fotos sejam enviadas para modelos sem suporte à visão.
- Adicionado aviso imediato quando um Character Card PNG e enviado como foto no Telegram,
  preservando o estado de importacao para o reenvio como arquivo.
- Incluído Git apenas no estágio de build para instalar a dependência fixada por commit.
- Adicionado build real da imagem Docker ao CI.
- Impedida a reinstalação de dependências de desenvolvimento quando os containers iniciam.
- Unificada a imagem de bot, worker e migração e excluída a configuração local do contexto Docker.
- Configurado o event loop compatível com Psycopg nos testes de integração executados no Windows.

### Added

- Monólito modular com adaptador Telegram, LiteLLM e PostgreSQL.
- Importação/exportação de Character Cards V1–V3 em JSON e PNG.
- Persona, episódios de conversa e entrega idempotente.
- Ledger auditável, memória imediata, forget, supersede e projeções Markdown.
- Dream worker com watermark, evidência, retries, locks e alusões pós-entrega.
- Docker Compose, backup diário, migração Alembic e suíte de avaliação com 27 cenários.
