# Temporal experiment

Self-hosted [Temporal](https://temporal.io/) via **Podman**, mirroring the launchd/n8n stock-fetch examples:

| Use case | launchd equivalent | n8n equivalent | Temporal |
| -------- | ------------------- | -------------- | -------- |
| Cron | `fetch-aapl` plist | `fetch-stock-cron-aapl` workflow | `fetch-stock-cron-aapl` **Schedule** (native, every 5 min) |
| On demand + input | `runner.py --name fetch-aapl -- … AAPL` | webhook `POST /webhook/fetch-stock` | `scripts/run-on-demand.sh AAPL` (starts + waits for the Workflow) |
| Agentic (Notion → LLM) | — | `Notion task summary` (poll + OpenRouter) | `scripts/run-notion-summary.sh <page_id>` (`NotionTaskSummaryWorkflow`) |

Stock cron + on-demand run the **same** `FetchStockWorkflow` (`workflows/fetch_stock.py`). Telegram failure alerts use the same env vars as launchd/n8n (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

The Notion flow mirrors n8n’s agentic summary (OpenRouter `deepseek/deepseek-v4-flash`, Spanish 2–3 sentences) but is **on-demand only** — pass a page id/URL; no Notion poll Schedule.

## Layout

```
temporal/
  compose.yaml            # temporal dev server (single binary + Web UI) + python worker
  requirements.txt        # temporalio SDK
  worker.py                # connects to the server, polls the 'stock-tasks' queue
  workflows/fetch_stock.py # FetchStockWorkflow + fetch_quote/notify_telegram activities
  workflows/notion_task_summary.py  # Notion → OpenRouter summary
  scripts/up.sh             # podman compose up
  scripts/schedule-cron.sh  # create/update the cron Schedule
  scripts/run-on-demand.sh  # start + wait for a one-off run, prints JSON result
  scripts/run-notion-summary.sh  # Notion page id → Spanish summary JSON
  .env.example
```

## Setup

1. Copy env and set secrets:

   ```bash
   cd temporal
   cp .env.example .env
   # optional: TELEGRAM_* for failure alerts
   # for Notion summary: NOTION_TOKEN + OPENROUTER_API_KEY
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

## Try the Notion summary (agentic)

Needs `NOTION_TOKEN` (integration must share the page) and `OPENROUTER_API_KEY` in `.env`, then recreate the worker (`./scripts/up.sh`).

```bash
./scripts/run-notion-summary.sh '<notion-page-id-or-url>'
```

Result shape: `{ok, exit_code, job_name, page_id, summary, url}` (success) or `{ok:false, error, ...}` on failure. No Telegram on success — print-only, like the stock on-demand script.

```
❯ ./scripts/run-notion-summary.sh https://app.notion.com/p/...
{
  "workflowId": "notion-summary-3d47810f-1790155464",
  "runId": "01a0cd94-9fad-73bc-a5aa-9f0852839c74",
  "type": "NotionTaskSummaryWorkflow",
  "namespace": "default",
  "taskQueue": "stock-tasks",
  "durationMillis": 14130,
  "status": "COMPLETED",
  "closeEvent": {
    "eventId": "17",
    "eventTime": "2026-09-23T09:24:38.729547214Z",
    "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
    "taskId": "3146218",
    "workflowExecutionCompletedEventAttributes": {
      "result": [
        {
          "exit_code": 0,
          "job_name": "notion-task-summary",
          "ok": true,
          "page_id": "3d47810f-380f-80d7-b61d-e8b5556dff98",
          "summary": "...",
          "url": "https://app.notion.com/p/..."
        }
      ],
      "workflowTaskCompletedEventId": "16"
    }
  },
  "result": {
    "exit_code": 0,
    "job_name": "notion-task-summary",
    "ok": true,
    "page_id": "3d47810f-380f-80d7-b61d-e8b5556dff98",
    "summary": "...",
    "url": "https://app.notion.com/p/..."
  }
}
```

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
