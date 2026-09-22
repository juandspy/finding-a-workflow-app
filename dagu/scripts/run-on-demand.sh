#!/usr/bin/env bash
# On-demand run, equivalent to n8n's `curl -X POST /webhook/fetch-stock`.
# `dagu start` runs synchronously and prints a step tree with stdout inline.
#
# Usage: ./scripts/run-on-demand.sh TICKER
set -euo pipefail

TICKER="${1:?Usage: run-on-demand.sh TICKER}"
CONTAINER="${DAGU_CONTAINER:-finding-a-workflow-dagu}"

podman exec "$CONTAINER" dagu start /var/lib/dagu/dags/fetch-stock-on-demand.yaml -- "TICKER=$TICKER"
