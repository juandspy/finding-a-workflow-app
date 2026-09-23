#!/usr/bin/env bash
# On-demand Notion page summary (mirrors n8n Notion task summary, minus poll trigger).
# Starts NotionTaskSummaryWorkflow and blocks until it completes, printing JSON.
#
# Usage: ./scripts/run-notion-summary.sh <notion-page-id-or-url>
set -euo pipefail

RAW="${1:?Usage: run-notion-summary.sh <notion-page-id-or-url>}"
CONTAINER="${TEMPORAL_CONTAINER:-finding-a-workflow-temporal}"

# Accept full Notion URL or bare id (with/without dashes).
PAGE_ID="$(python3 -c '
import re, sys
raw = sys.argv[1].strip()
m = re.search(
    r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    raw,
)
print(m.group(1) if m else raw)
' "$RAW")"

SHORT="$(echo "$PAGE_ID" | tr -d '-' | cut -c1-8)"
WORKFLOW_ID="notion-summary-${SHORT}-$(date +%s)"
INPUT="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$PAGE_ID")"

podman exec "$CONTAINER" temporal workflow execute \
  --workflow-id "$WORKFLOW_ID" \
  --task-queue stock-tasks \
  --type NotionTaskSummaryWorkflow \
  --input "$INPUT" \
  -o json
