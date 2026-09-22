#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VOLUME="${N8N_VOLUME:-finding-a-workflow-n8n-data}"

if [[ ! -f .env ]]; then
  echo "Missing .env — run: cp .env.example .env && edit N8N_ENCRYPTION_KEY"
  exit 1
fi

mkdir -p data workflows

podman volume exists "$VOLUME" >/dev/null 2>&1 || podman volume create "$VOLUME"

# One-time migration from legacy host ./data bind mount (with correct ownership for node user).
if [[ -f data/database.sqlite ]] && ! podman run --rm -v "$VOLUME":/target docker.io/library/alpine:3.20 test -f /target/database.sqlite; then
  echo "Migrating ./data into Podman volume $VOLUME ..."
  podman run --rm -v "$VOLUME":/target -v "$ROOT/data":/source:ro docker.io/library/alpine:3.20 sh -c 'cp -a /source/. /target/'
  podman run --rm --user root -v "$VOLUME":/home/node/.n8n --entrypoint chown docker.io/n8nio/n8n:latest -R node:node /home/node/.n8n
fi

if command -v podman-compose >/dev/null 2>&1; then
  podman-compose up -d
elif podman compose version >/dev/null 2>&1; then
  podman compose up -d
else
  echo "Need podman compose or podman-compose"
  exit 1
fi

echo "n8n: http://localhost:${N8N_PORT:-5678}"
