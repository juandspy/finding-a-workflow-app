#!/usr/bin/env python3
"""Example cron job: fetch a public quote for a ticker and print it (stdlib only)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

# Free demo endpoint — swap for your real market-data API.
USER_AGENT = "finding-a-workflow-app/launchd (example)"


def chart_url(ticker: str) -> str:
    symbol = urllib.parse.quote(ticker.upper())
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?interval=1d&range=1d"
    )


def fetch_quote(ticker: str) -> int:
    req = urllib.request.Request(chart_url(ticker), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    try:
        meta = payload["chart"]["result"][0]["meta"]
        symbol = meta["symbol"]
        price = meta["regularMarketPrice"]
    except (KeyError, IndexError, TypeError) as exc:
        print(f"unexpected response shape: {exc}", file=sys.stderr)
        print(payload, file=sys.stderr)
        return 1

    print(f"{symbol}={price}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a Yahoo Finance quote for a ticker.")
    parser.add_argument(
        "ticker",
        help="Stock symbol (e.g. AAPL, TSLA)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return fetch_quote(args.ticker)


if __name__ == "__main__":
    raise SystemExit(main())
