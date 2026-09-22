# dagu experiment

Self-hosted [dagu](https://dagu.sh/) via **Podman** (single binary, no DB), mirroring the launchd/n8n/temporal stock-fetch examples:

| Use case | launchd equivalent | Temporal equivalent | dagu |
| -------- | ------------------- | -------------------- | ---- |
| Cron | `fetch-aapl` plist | `fetch-stock-cron-aapl` Schedule | `dags/fetch-stock-cron-aapl.yaml` (`schedule:`, every 5 min) |
| On demand + input | `runner.py --name fetch-aapl -- … AAPL` | `scripts/run-on-demand.sh AAPL` | `scripts/run-on-demand.sh AAPL` (`dagu start ... -- TICKER=AAPL`) |

Both DAGs run the same `scripts/fetch_stock.sh` (curl + jq — both ship in the base image, no Python needed). Telegram failure alerts use the same env vars as launchd/n8n/temporal (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), wired via each DAG's `handler_on.failure`.

Agentic workflows are **not** included — dagu has no visual editor either; you'd write a DAG YAML calling whatever script/agent you want, no different from any other step.

## Layout

```
dagu/
  compose.yaml                       # single container: dagu start-all (server + scheduler)
  dags/fetch-stock-cron-aapl.yaml     # schedule + catchup_window + handler_on.failure
  dags/fetch-stock-on-demand.yaml     # same step, no schedule, triggered with params
  scripts/fetch_stock.sh              # shared fetch logic (curl + jq)
  scripts/up.sh                        # podman compose up
  scripts/run-on-demand.sh             # dagu start ... -- TICKER=<ticker>
  .env.example
```

## Setup

1. Copy env and set secrets (optional — only needed for Telegram alerts):

   ```bash
   cd dagu
   cp .env.example .env
   ```

2. Start dagu:

   ```bash
   chmod +x scripts/*.sh
   ./scripts/up.sh
   ```

   Open http://localhost:8080 for the Web UI (no login — `DAGU_AUTH_MODE=none` for this PoC).

## Try the on-demand DAG

```bash
time ./scripts/run-on-demand.sh IBM
```

`dagu start` runs synchronously and prints the step tree with output inline:

```
Succeeded - 2026-09-18T11:24:17+02:00

dag: fetch-stock-on-demand (0s)
├─fetch (0s) [succeeded]
│ └─stdout: {"ok":true,"exit_code":0,"job_name":"fetch-ibm","ticker":"IBM","symbol":"IBM","price":237.75,"output":"IBM=237.75"}
./scripts/run-on-demand.sh IBM  0.01s user 0.01s system 6% cpu 0.408 total
```

Same JSON shape as the n8n webhook / Temporal on-demand result.

## Add more tickers (cron)

Copy `dags/fetch-stock-cron-aapl.yaml`, rename, change the `TICKER` default and the `schedule`. It's picked up automatically — no import/restart step, dagu watches the `dags/` directory.

## Stop / remove

```bash
cd dagu
podman compose down
# state persists in Podman volume finding-a-workflow-dagu-data
```

## Notes vs n8n / Temporal

- **Logs & exit codes**: per-step stdout/stderr logs on disk under the data volume, browsable in the Web UI (Executions tab) same as n8n; unlike n8n, log *files* are also directly on disk if you want to `grep` them without the UI.
- **Offline catch-up**: real ✅, same as Temporal. `catchup_window: "1h"` on the cron DAG — on first start with no prior state, dagu treated the last hour as missed and ran a `catchup-*` run immediately (visible in the Web UI history).
- **No built-in webhook trigger**: like Temporal, there's no HTTP node/webhook concept — `run-on-demand.sh` shells into the container and uses the bundled `dagu` CLI. (dagu does have a REST API — `POST /api/v1/dags/{file}/start` — if you want an actual HTTP trigger instead of `podman exec`.)
- **Simplicity**: single container, single binary, no separate worker process (unlike Temporal's server+worker split). Closest to launchd in spirit, but with a real UI, catch-up, and retries.
