#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${N8N_CONTAINER:-finding-a-workflow-n8n}"
VOLUME="${N8N_VOLUME:-finding-a-workflow-n8n-data}"

compose() {
  if command -v podman-compose >/dev/null 2>&1; then
    podman-compose "$@"
  else
    podman compose "$@"
  fi
}

echo "Stopping $CONTAINER..."
compose stop >/dev/null 2>&1 || podman stop "$CONTAINER" >/dev/null 2>&1 || true

echo "Repairing SQLite in volume $VOLUME (journal_mode=DELETE, drop WAL sidecars)..."
podman run --rm \
  -v "$VOLUME":/data \
  docker.io/library/alpine:3.20 \
  sh -ec '
    command -v sqlite3 >/dev/null || apk add --no-cache sqlite >/dev/null
    if [[ ! -f /data/database.sqlite ]]; then
      echo "No /data/database.sqlite in volume — nothing to repair."
      exit 0
    fi
    sqlite3 /data/database.sqlite "PRAGMA journal_mode=DELETE; PRAGMA integrity_check;"
    rm -f /data/database.sqlite-wal /data/database.sqlite-shm
  '

podman run --rm --user root -v "$VOLUME":/home/node/.n8n --entrypoint chown docker.io/n8nio/n8n:latest -R node:node /home/node/.n8n >/dev/null 2>&1 || true

echo "Starting $CONTAINER..."
compose start >/dev/null 2>&1 || podman start "$CONTAINER" >/dev/null

echo "Repair complete. If errors persist: ./scripts/import-workflows.sh --reset"
