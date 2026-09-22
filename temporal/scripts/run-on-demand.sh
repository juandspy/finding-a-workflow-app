#!/usr/bin/env bash
# On-demand run, equivalent to n8n's `curl -X POST /webhook/fetch-stock`.
# Starts the workflow and blocks until it completes, printing the JSON result.
#
# Usage: ./scripts/run-on-demand.sh TICKER
set -euo pipefail

TICKER="${1:?Usage: run-on-demand.sh TICKER}"
CONTAINER="${TEMPORAL_CONTAINER:-finding-a-workflow-temporal}"
TICKER_LOWER="$(echo "$TICKER" | tr '[:upper:]' '[:lower:]')"
WORKFLOW_ID="fetch-${TICKER_LOWER}-$(date +%s)"

podman exec "$CONTAINER" temporal workflow execute \
  --workflow-id "$WORKFLOW_ID" \
  --task-queue stock-tasks \
  --type FetchStockWorkflow \
  --input "\"$TICKER\"" \
  -o json
