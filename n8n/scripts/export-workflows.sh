#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${N8N_CONTAINER:-finding-a-workflow-n8n}"
WORKFLOWS_DIR="${ROOT}/workflows"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

command -v python3 >/dev/null || { echo "python3 is required on the host"; exit 1; }

compose() {
  if command -v podman-compose >/dev/null 2>&1; then
    podman-compose "$@"
  else
    podman compose "$@"
  fi
}

export_workflow() {
  local wf_id="$1"
  if podman ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
    podman exec -u node "$CONTAINER" n8n export:workflow --id="$wf_id"
  else
    compose run --rm --no-deps --entrypoint n8n n8n export:workflow --id="$wf_id" </dev/null
  fi
}

EXPORTED=0
for wf_file in "$WORKFLOWS_DIR"/*.json; do
  [[ -e "$wf_file" ]] || continue
  wf_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["id"])' "$wf_file")"
  echo "Exporting $wf_id -> $(basename "$wf_file") ..."
  export_workflow "$wf_id" | python3 "$SCRIPT_DIR/workflow_json.py" write "$wf_file"
  EXPORTED=$((EXPORTED + 1))
done

echo "Exported $EXPORTED workflow(s) from n8n into n8n/workflows/."
