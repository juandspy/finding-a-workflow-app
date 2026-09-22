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

DRIFT=0
CHECKED=0
for wf_file in "$WORKFLOWS_DIR"/*.json; do
  [[ -e "$wf_file" ]] || continue
  wf_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["id"])' "$wf_file")"
  CHECKED=$((CHECKED + 1))
  if ! export_workflow "$wf_id" | python3 "$SCRIPT_DIR/workflow_json.py" check "$wf_file"; then
    DRIFT=$((DRIFT + 1))
  fi
done

if [[ "$DRIFT" -gt 0 ]]; then
  echo "$DRIFT of $CHECKED workflow(s) differ from n8n/workflows/*.json."
  echo "Run ./scripts/export-workflows.sh to pull UI changes into git."
  exit 1
fi

echo "All $CHECKED workflow(s) match n8n (nodes, connections, settings, name, active)."
