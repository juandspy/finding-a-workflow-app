#!/usr/bin/env bash
# Create (or update) the Temporal Schedule that mirrors launchd's fetch-aapl
# plist / n8n's fetch-stock-cron-aapl workflow.
#
# Usage: ./scripts/schedule-cron.sh [TICKER] [CRON]
#   ./scripts/schedule-cron.sh              # AAPL every 5 minutes
#   ./scripts/schedule-cron.sh IBM "*/2 * * * *"
set -euo pipefail

TICKER="${1:-AAPL}"
CRON="${2:-*/5 * * * *}"
TICKER_LOWER="$(echo "$TICKER" | tr '[:upper:]' '[:lower:]')"
SCHEDULE_ID="fetch-stock-cron-${TICKER_LOWER}"
CONTAINER="${TEMPORAL_CONTAINER:-finding-a-workflow-temporal}"

temporal_cli() {
  podman exec "$CONTAINER" temporal "$@"
}

ARGS=(
  --schedule-id "$SCHEDULE_ID"
  --cron "$CRON"
  --catchup-window 1h
  --overlap-policy Skip
  --workflow-id "${SCHEDULE_ID}-run"
  --task-queue stock-tasks
  --type FetchStockWorkflow
  --input "\"$TICKER\""
)

if temporal_cli schedule describe --schedule-id "$SCHEDULE_ID" >/dev/null 2>&1; then
  echo "Updating schedule $SCHEDULE_ID ..."
  temporal_cli schedule update "${ARGS[@]}"
else
  echo "Creating schedule $SCHEDULE_ID ..."
  temporal_cli schedule create "${ARGS[@]}"
fi

echo "Scheduled: $SCHEDULE_ID  cron='$CRON'  ticker=$TICKER  (catch-up window: 1h)"
