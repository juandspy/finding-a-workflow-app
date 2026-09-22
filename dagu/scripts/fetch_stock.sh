#!/usr/bin/env bash
# Fetch a public quote for a ticker (curl + jq only — both ship in the
# ghcr.io/dagucloud/dagu:latest image). Mirrors launchd/jobs/fetch_stocks.py
# and the n8n/temporal equivalents: same endpoint, same JSON output shape.
set -uo pipefail

TICKER="${1:?Usage: fetch_stock.sh TICKER}"
SYMBOL="$(echo "$TICKER" | tr '[:lower:]' '[:upper:]')"
JOB_NAME="fetch-$(echo "$TICKER" | tr '[:upper:]' '[:lower:]')"
URL="https://query1.finance.yahoo.com/v8/finance/chart/${SYMBOL}?interval=1d&range=1d"

fail() {
  echo "{\"ok\":false,\"exit_code\":1,\"job_name\":\"$JOB_NAME\",\"ticker\":\"$TICKER\",\"error\":\"$1\"}"
  exit 1
}

RESPONSE="$(curl -fsS --max-time 30 -A "finding-a-workflow-app/dagu (example)" "$URL")" || fail "fetch failed"

PRICE="$(echo "$RESPONSE" | jq -r '.chart.result[0].meta.regularMarketPrice // empty')"
RESOLVED_SYMBOL="$(echo "$RESPONSE" | jq -r '.chart.result[0].meta.symbol // empty')"

if [[ -z "$PRICE" || -z "$RESOLVED_SYMBOL" ]]; then
  fail "unexpected response shape"
fi

echo "{\"ok\":true,\"exit_code\":0,\"job_name\":\"$JOB_NAME\",\"ticker\":\"$TICKER\",\"symbol\":\"$RESOLVED_SYMBOL\",\"price\":$PRICE,\"output\":\"$RESOLVED_SYMBOL=$PRICE\"}"
