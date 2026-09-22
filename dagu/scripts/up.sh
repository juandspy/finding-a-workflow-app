#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VOLUME="${DAGU_VOLUME:-finding-a-workflow-dagu-data}"

podman volume exists "$VOLUME" >/dev/null 2>&1 || podman volume create "$VOLUME"

if command -v podman-compose >/dev/null 2>&1; then
  podman-compose up -d
elif podman compose version >/dev/null 2>&1; then
  podman compose up -d
else
  echo "Need podman compose or podman-compose"
  exit 1
fi

echo "dagu Web UI: http://localhost:8080"
