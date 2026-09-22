# Temporal experiment

Self-hosted [Temporal](https://temporal.io/) via **Podman**, mirroring the launchd/n8n stock-fetch examples:

| Use case | launchd equivalent | n8n equivalent | Temporal |
| -------- | ------------------- | -------------- | -------- |
| Cron | `fetch-aapl` plist | `fetch-stock-cron-aapl` workflow | `fetch-stock-cron-aapl` **Schedule** (native, every 5 min) |
| On demand + input | `runner.py --name fetch-aapl -- … AAPL` | webhook `POST /webhook/fetch-stock` | `scripts/run-on-demand.sh AAPL` (starts + waits for the Workflow) |

Both triggers run the **same** `FetchStockWorkflow` (`workflows/fetch_stock.py`) — one Workflow type, two ways to start it. Telegram failure alerts use the same env vars as launchd/n8n (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

Agentic workflows are **not** included here — Temporal is code-first (no visual editor), so that's just regular Python you'd write in `workflows/`.

## Layout

```
temporal/
  compose.yaml            # temporal dev server (single binary + Web UI) + python worker
  requirements.txt        # temporalio SDK
  worker.py                # connects to the server, polls the 'stock-tasks' queue
  workflows/fetch_stock.py # FetchStockWorkflow + fetch_quote/notify_telegram activities
  scripts/up.sh             # podman compose up
  scripts/schedule-cron.sh  # create/update the cron Schedule
  scripts/run-on-demand.sh  # start + wait for a one-off run, prints JSON result
  .env.example
```

## Setup

1. Copy env and set secrets (optional — only needed for Telegram alerts):

   ```bash
   cd temporal
   cp .env.example .env
   ```

2. Start the Temporal dev server + worker:

   ```bash
   chmod +x scripts/*.sh
   ./scripts/up.sh
   ```

   Open http://localhost:8233 for the Web UI. The worker container installs `temporalio` on first start — tail it with `podman logs -f finding-a-workflow-temporal-worker` if `run-on-demand.sh` fails with "no worker polling".

## Try the on-demand workflow

```bash
time ./scripts/run-on-demand.sh IBM
```

Starts `FetchStockWorkflow`, blocks until it completes, and prints the JSON result (`workflowId`, `status`, `result: {ok, exit_code, symbol, price, output}`) — same shape as the n8n webhook response.

## Add the cron Schedule

```bash
./scripts/schedule-cron.sh AAPL          # every 5 minutes, 1h catch-up window
./scripts/schedule-cron.sh IBM "*/2 * * * *"
```

Re-running with the same ticker updates the existing Schedule instead of erroring. Inspect it in the Web UI under **Schedules**, or:

```bash
podman exec finding-a-workflow-temporal temporal schedule describe --schedule-id fetch-stock-cron-aapl
```

## Stop / remove

```bash
cd temporal
podman compose down
# DB persists in Podman volume finding-a-workflow-temporal-data (--db-filename on the dev server)
```

## Notes vs n8n / launchd

- **Logs & exit codes**: every Workflow/Activity run is in the Web UI (Event History), with full retry attempts — richer than n8n's Executions tab.
- **Offline catch-up**: real ✅ here. Schedules have a `--catchup-window` (set to `1h`); if the server was down when a run was due, it fires on recovery instead of being silently skipped, unlike n8n/launchd.
- **No built-in webhook**: Temporal has no HTTP trigger concept. `run-on-demand.sh` shells into the server container and uses the bundled `temporal` CLI (`workflow execute`) — no separate client install needed on the host.
- **Retries are automatic**: `fetch_quote` retries up to 3 times (Temporal's built-in `RetryPolicy`) before the Workflow gives up and notifies Telegram — this was manual/absent in the launchd and n8n versions.
