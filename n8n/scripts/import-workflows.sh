#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${N8N_CONTAINER:-finding-a-workflow-n8n}"
WORKFLOWS_DIR="${ROOT}/workflows"
VOLUME="${N8N_VOLUME:-finding-a-workflow-n8n-data}"

if [[ ! -d "$WORKFLOWS_DIR" ]]; then
  echo "Missing workflows dir: $WORKFLOWS_DIR"
  exit 1
fi

command -v python3 >/dev/null || { echo "python3 is required on the host"; exit 1; }

RESET=0
if [[ "${1:-}" == "--reset" ]]; then
  RESET=1
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--reset]"
  exit 1
fi

compose() {
  if command -v podman-compose >/dev/null 2>&1; then
    podman-compose "$@"
  else
    podman compose "$@"
  fi
}

n8n_cli() {
  compose run --rm --no-deps --entrypoint n8n n8n "$@" </dev/null
}

echo "Stopping $CONTAINER..."
compose stop >/dev/null 2>&1 || podman stop "$CONTAINER" >/dev/null 2>&1 || true

if [[ "$RESET" -eq 1 ]]; then
  echo "Resetting n8n database in volume $VOLUME ..."
  podman run --rm -v "$VOLUME":/data docker.io/library/alpine:3.20 \
    sh -c 'rm -f /data/database.sqlite /data/database.sqlite-wal /data/database.sqlite-shm'
  echo "Database wiped. You will need to recreate the owner account at http://localhost:5678."
fi

echo "Importing workflows via n8n CLI ..."
n8n_cli import:workflow --separate --input=/workflows

IMPORTED=0
for wf_file in "$WORKFLOWS_DIR"/*.json; do
  [[ -e "$wf_file" ]] || continue
  read -r wf_id wf_name < <(
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(d["id"], d["name"])' "$wf_file"
  )
  echo "Publishing $wf_name ($wf_id) ..."
  n8n_cli publish:workflow --id="$wf_id"
  IMPORTED=$((IMPORTED + 1))
done

echo "Starting $CONTAINER ..."
compose start >/dev/null 2>&1 || podman start "$CONTAINER" >/dev/null

echo "Imported and published $IMPORTED workflow(s) from n8n/workflows/ (stable IDs; re-import overwrites in place)."
