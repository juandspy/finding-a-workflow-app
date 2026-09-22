#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VOLUME="${TEMPORAL_VOLUME:-finding-a-workflow-temporal-data}"

podman volume exists "$VOLUME" >/dev/null 2>&1 || podman volume create "$VOLUME"

if command -v podman-compose >/dev/null 2>&1; then
  podman-compose up -d
elif podman compose version >/dev/null 2>&1; then
  podman compose up -d
else
  echo "Need podman compose or podman-compose"
  exit 1
fi

echo "Temporal Web UI: http://localhost:8233"
echo "Worker installs deps on first start — tail it with:"
echo "  podman logs -f finding-a-workflow-temporal-worker"
