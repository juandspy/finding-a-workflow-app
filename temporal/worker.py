"""Temporal worker process: connects to the dev server and polls the task queue."""

from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from workflows.fetch_stock import FetchStockWorkflow, fetch_quote, notify_telegram

TASK_QUEUE = "stock-tasks"


async def main() -> None:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    client = await Client.connect(address)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[FetchStockWorkflow],
        activities=[fetch_quote, notify_telegram],
    )
    print(f"Worker started, connected to {address}, task queue '{TASK_QUEUE}'")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
