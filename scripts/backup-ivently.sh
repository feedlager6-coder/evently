#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/ivently/postgres"
DATE=$(date +"%Y%m%d_%H%M%S")
FILENAME="${BACKUP_DIR}/ivently_backup_${DATE}.dump"

mkdir -p "${BACKUP_DIR}"

# Execute pg_dump from container
docker compose -f /opt/ivently/docker-compose.yml exec -T db pg_dump \
    -U ivently_user \
    -d ivently_prod \
    --format=custom \
    --no-owner \
    --no-acl > "${FILENAME}"

# Retain backups for 14 days
find "${BACKUP_DIR}" -type f -name "*.dump" -mtime +14 -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup successfully created: ${FILENAME} ($(stat -c%s "${FILENAME}") bytes)"
