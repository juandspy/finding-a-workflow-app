"""Shared workflow + activities for fetching a stock quote (Temporal PoC).

Mirrors launchd/jobs/fetch_stocks.py and n8n's fetch-stock workflows: same
Yahoo Finance endpoint, same TELEGRAM_* failure notification. One workflow
type serves both the cron Schedule and the on-demand trigger.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

USER_AGENT = "finding-a-workflow-app/temporal (example)"


def _chart_url(ticker: str) -> str:
    symbol = urllib.parse.quote(ticker.upper())
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"


@dataclass
class Quote:
    symbol: str
    price: float


@activity.defn
async def fetch_quote(ticker: str) -> Quote:
    req = urllib.request.Request(_chart_url(ticker), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApplicationError(f"fetch failed: {exc}") from exc

    try:
        meta = payload["chart"]["result"][0]["meta"]
        return Quote(symbol=meta["symbol"], price=meta["regularMarketPrice"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ApplicationError(f"unexpected response shape: {exc}") from exc


@activity.defn
async def notify_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        activity.logger.info("Telegram not configured, skipping: %s", message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as exc:
        activity.logger.warning("Telegram notify failed: %s", exc)


@workflow.defn
class FetchStockWorkflow:
    @workflow.run
    async def run(self, ticker: str) -> dict:
        job_name = f"fetch-{ticker.lower()}"
        try:
            quote = await workflow.execute_activity(
                fetch_quote,
                ticker,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        except Exception as exc:
            await workflow.execute_activity(
                notify_telegram,
                f"[{job_name}] failed: {exc}",
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {
                "ok": False,
                "exit_code": 1,
                "job_name": job_name,
                "ticker": ticker,
                "error": str(exc),
            }

        return {
            "ok": True,
            "exit_code": 0,
            "job_name": job_name,
            "ticker": ticker,
            "symbol": quote.symbol,
            "price": quote.price,
            "output": f"{quote.symbol}={quote.price}",
        }
