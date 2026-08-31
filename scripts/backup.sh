#!/bin/sh
set -eu

backup_once() {
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p /backups
  pg_dump --format=custom --file="/backups/postgres-${stamp}.dump"
  tar -czf "/backups/files-${stamp}.tar.gz" -C /data cards config
  find /backups -type f -mtime +6 -delete
}

if [ "${1:-}" = "loop" ]; then
  while true; do
    backup_once
    sleep 86400
  done
else
  backup_once
fi

