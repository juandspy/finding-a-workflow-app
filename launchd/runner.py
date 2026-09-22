#!/usr/bin/env python3
"""Run a command, persist logs + exit codes, optionally notify via Telegram."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
RUNS_FILE = DATA_DIR / "runs.jsonl"
ENV_FILE = ROOT / ".env"


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print(
            "telegram: skipped (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)",
            file=sys.stderr,
        )
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
        if not json.loads(body).get("ok"):
            print(f"telegram: unexpected response: {body}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"telegram: failed to send: {exc}", file=sys.stderr)


def append_run(record: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with RUNS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def should_notify(mode: str, exit_code: int) -> bool:
    """
    Determine whether to send a Telegram notification based on the notification mode and exit code.

    Args:
        mode: The notification mode ("always", "never", anything else is treated as "failure").
        exit_code: The exit code of the command.

    Returns:
        True if a notification should be sent, False otherwise.
    """
    if mode == "never":
        return False
    if mode == "always":
        return True
    return exit_code != 0  # failure


def run(name: str, argv: list[str], notify: str, cwd: Path | None) -> int:
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    job_log_dir = LOGS_DIR / name
    job_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = job_log_dir / f"{stamp}.log"

    header = (
        f"job={name}\n"
        f"started={started.isoformat()}\n"
        f"cwd={cwd or Path.cwd()}\n"
        f"cmd={' '.join(argv)}\n"
        f"{'=' * 60}\n"
    )

    with log_path.open("w", encoding="utf-8") as log:
        log.write(header)
        log.flush()
        proc = subprocess.run(
            argv,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        exit_code = proc.returncode
        finished = datetime.now(timezone.utc)
        log.write(f"\n{'=' * 60}\n")
        log.write(f"finished={finished.isoformat()}\n")
        log.write(f"exit_code={exit_code}\n")

    record = {
        "name": name,
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "exit_code": exit_code,
        "log": str(log_path.relative_to(ROOT)),
        "cmd": argv,
    }
    append_run(record)

    status = "OK" if exit_code == 0 else "FAIL"
    print(f"[{status}] {name} exit={exit_code} log={log_path}")

    if should_notify(notify, exit_code):
        duration = (finished - started).total_seconds()
        send_telegram(
            f"launchd job {status}: {name}\n"
            f"exit_code={exit_code}\n"
            f"duration={duration:.1f}s\n"
            f"log={log_path.name}"
        )

    return exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrap a command with logs, exit-code history, and Telegram alerts."
    )
    parser.add_argument("--name", required=True, help="Job name used in logs/runs")
    parser.add_argument(
        "--notify",
        choices=("failure", "always", "never"),
        default="failure",
        help="When to send Telegram messages (default: failure)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory for the command (default: current dir)",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run; put -- before it if needed",
    )
    args = parser.parse_args(argv)
    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.error("missing command to run (example: -- python jobs/fetch_stocks.py)")
    args.command = cmd
    return args


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args.name, args.command, args.notify, args.cwd)


if __name__ == "__main__":
    raise SystemExit(main())
