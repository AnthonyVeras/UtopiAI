# Operações

## Preparação

1. Instale Docker/Compose na VPS e clone o repositório.
2. Copie `.env.example` para `.env` e gere senha forte para Postgres.
3. Copie `config/llm_profiles.example.toml` para `config/llm_profiles.toml`.
4. Configure token Telegram, allowlist e chaves dos perfis.
5. Rode `docker compose config` para validar e `docker compose up -d --build`.

PostgreSQL não publica porta. `migrate` espera o healthcheck e termina antes de bot/worker. Veja
logs com `docker compose logs -f bot worker`; nunca habilite dump de prompt em produção.

## Migração e rollback

```bash
docker compose run --rm migrate
docker compose run --rm bot uv run alembic current
```

Antes de downgrade, faça backup. Downgrade do baseline apaga todas as tabelas e só deve ser usado
em ambiente descartável.

## Backup

O serviço `backup` cria um `pg_dump` custom e um tar de cards/configuração a cada 24 horas, retendo
sete dias no volume `backups`. Para executar sob demanda:

```bash
docker compose run --rm backup sh /usr/local/bin/backup.sh
```

O TOML não contém chaves; `.env` não entra no arquivo. Para produção, programe o primeiro start do
serviço no horário noturno desejado. Backup externo é obrigatório antes de beta multiusuário.

## Restauração

Pare bot e worker, preserve o estado atual e confirme os nomes exatos dos arquivos:

```bash
docker compose stop bot worker backup
docker compose exec -T postgres dropdb -U utopiai --if-exists utopiai
docker compose exec -T postgres createdb -U utopiai utopiai
docker compose exec -T postgres pg_restore -U utopiai -d utopiai --clean --if-exists /backup.dump
```

O último comando pressupõe que o dump foi copiado para o container. Restaure o tar nos volumes de
cards/config, rode migrações e então suba serviços. Faça um ensaio de restauração antes do deploy.

## Diagnóstico

- `/status`: banco, perfis e dream pendente;
- `/sonhos`: runs e falhas recentes;
- `llm_calls`: tokens, custo estimado, latência e erro sem conteúdo;
- `dream_runs`: tentativas, watermark e resumo;
- `/repetir`: recria geração a partir da última mensagem que falhou.

O build da imagem, a migração e o smoke test de bot/worker devem ser registrados no handoff de
cada release. `migrate` é o único serviço que declara o build; bot e worker reutilizam a mesma
imagem para evitar builds concorrentes com a mesma tag.

