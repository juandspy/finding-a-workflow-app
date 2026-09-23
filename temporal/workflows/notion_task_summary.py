"""On-demand Notion page → OpenRouter summary (mirrors n8n Notion task summary).

Trigger: scripts/run-notion-summary.sh <page_id>
No Schedule / poll — page id is passed in. Success result is JSON only;
Telegram only on failure (same as FetchStockWorkflow).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

NOTION_VERSION = "2022-06-28"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"


def _normalize_page_id(page_id: str) -> str:
    raw = page_id.strip().replace("-", "")
    if len(raw) == 32 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
    return page_id.strip()


def _notion_request(method: str, path: str, token: str) -> Any:
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise ApplicationError(f"Notion {method} {path} failed ({exc.code}): {body}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApplicationError(f"Notion {method} {path} failed: {exc}") from exc


def _rich_text(parts: list[dict[str, Any]] | None) -> str:
    if not parts:
        return ""
    return "".join(p.get("plain_text", "") for p in parts)


def _prop_value(prop: dict[str, Any]) -> Any:
    kind = prop.get("type")
    if not kind:
        return None
    val = prop.get(kind)
    if kind == "title":
        return _rich_text(val)
    if kind == "rich_text":
        return _rich_text(val)
    if kind == "select":
        return (val or {}).get("name")
    if kind == "multi_select":
        return [x.get("name") for x in (val or [])]
    if kind == "status":
        return (val or {}).get("name")
    if kind == "date":
        if not val:
            return None
        return {"start": val.get("start"), "end": val.get("end")}
    if kind == "people":
        return [p.get("name") or p.get("id") for p in (val or [])]
    if kind == "url":
        return val
    if kind == "checkbox":
        return val
    if kind == "number":
        return val
    if kind == "email":
        return val
    if kind == "phone_number":
        return val
    if kind == "formula":
        return val
    if kind == "relation":
        return [r.get("id") for r in (val or [])]
    if kind == "unique_id":
        prefix = (val or {}).get("prefix")
        number = (val or {}).get("number")
        return f"{prefix}-{number}" if prefix else number
    return val


def _properties_summary(page: dict[str, Any]) -> dict[str, Any]:
    props = page.get("properties") or {}
    out: dict[str, Any] = {"id": page.get("id"), "url": page.get("url")}
    for name, prop in props.items():
        out[name] = _prop_value(prop)
    return out


def _block_to_md(block: dict[str, Any]) -> str:
    kind = block.get("type")
    data = block.get(kind) or {}
    text = _rich_text(data.get("rich_text"))
    if kind == "paragraph":
        return text
    if kind == "heading_1":
        return f"# {text}"
    if kind == "heading_2":
        return f"## {text}"
    if kind == "heading_3":
        return f"### {text}"
    if kind == "bulleted_list_item":
        return f"- {text}"
    if kind == "numbered_list_item":
        return f"1. {text}"
    if kind == "to_do":
        mark = "x" if data.get("checked") else " "
        return f"- [{mark}] {text}"
    if kind == "quote":
        return f"> {text}"
    if kind == "code":
        lang = data.get("language") or ""
        return f"```{lang}\n{text}\n```"
    if kind == "divider":
        return "---"
    if kind in ("unsupported", "child_page", "child_database"):
        return ""
    return text


def _list_block_children(token: str, block_id: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        payload = _notion_request("GET", path, token)
        blocks.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    return blocks


def _blocks_to_markdown(token: str, block_id: str, depth: int = 0) -> str:
    if depth > 5:
        return ""
    lines: list[str] = []
    for block in _list_block_children(token, block_id):
        line = _block_to_md(block)
        if line:
            lines.append(line)
        if block.get("has_children"):
            child_md = _blocks_to_markdown(token, block["id"], depth + 1)
            if child_md:
                indented = "\n".join(
                    ("  " + ln if ln else ln) for ln in child_md.splitlines()
                )
                lines.append(indented)
    return "\n".join(lines)


@dataclass
class NotionPageContent:
    page_id: str
    properties: dict[str, Any]
    markdown: str


@activity.defn
async def fetch_notion_markdown(page_id: str) -> NotionPageContent:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise ApplicationError("NOTION_TOKEN is not set")

    normalized = _normalize_page_id(page_id)
    page = _notion_request("GET", f"/pages/{normalized}", token)
    markdown = _blocks_to_markdown(token, normalized) or "(empty)"
    return NotionPageContent(
        page_id=page.get("id") or normalized,
        properties=_properties_summary(page),
        markdown=markdown,
    )


@activity.defn
async def summarize_openrouter(page: NotionPageContent) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ApplicationError("OPENROUTER_API_KEY is not set")

    prompt = (
        "Summarize this Notion task in Spanish (2-3 sentences).\n\n"
        f"## Properties\n{json.dumps(page.properties, ensure_ascii=False, indent=2)}\n\n"
        f"## Page content\n{page.markdown}"
    )
    body = json.dumps(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/finding-a-workflow-app",
            "X-Title": "finding-a-workflow-app temporal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode(errors="replace")
        raise ApplicationError(f"OpenRouter failed ({exc.code}): {err_body}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApplicationError(f"OpenRouter failed: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ApplicationError(f"unexpected OpenRouter response: {payload}") from exc

    if not isinstance(content, str) or not content.strip():
        raise ApplicationError("OpenRouter returned empty summary")
    return content.strip()


@workflow.defn
class NotionTaskSummaryWorkflow:
    @workflow.run
    async def run(self, page_id: str) -> dict:
        job_name = "notion-task-summary"
        try:
            page = await workflow.execute_activity(
                fetch_notion_markdown,
                page_id,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            summary = await workflow.execute_activity(
                summarize_openrouter,
                page,
                start_to_close_timeout=timedelta(seconds=90),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        except Exception as exc:
            await workflow.execute_activity(
                "notify_telegram",
                f"[{job_name}] failed: {exc}",
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {
                "ok": False,
                "exit_code": 1,
                "job_name": job_name,
                "page_id": page_id,
                "error": str(exc),
            }

        return {
            "ok": True,
            "exit_code": 0,
            "job_name": job_name,
            "page_id": page.page_id,
            "summary": summary,
            "url": page.properties.get("url"),
        }
