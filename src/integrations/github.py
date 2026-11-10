"""Async GitHub client with bounded retry and workflow-run synchronization."""

import asyncio
import logging
import os

import httpx

from config.settings import HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS, RETRY_BASE_SECONDS
from src.observability import get_logger, log_event

LOGGER = get_logger("github")


class GitHubClient:
    def __init__(self, repo: str, token: str | None = None, *, transport=None, sleep=asyncio.sleep):
        self.repo = repo
        token = token or os.getenv("GITHUB_TOKEN", "")
        self.h = {"Accept": "application/vnd.github+json"}
        if token:
            self.h["Authorization"] = f"Bearer {token}"
        self.api = "https://api.github.com"
        self.transport = transport
        self.sleep = sleep

    async def _request(self, method: str, path: str, body=None):
        last_error = None
        for attempt in range(1, HTTP_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    headers=self.h,
                    timeout=HTTP_TIMEOUT_SECONDS,
                    transport=self.transport,
                ) as client:
                    response = await client.request(method, f"{self.api}{path}", json=body)
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    )
                    if attempt < HTTP_MAX_RETRIES:
                        await self.sleep(delay)
                        continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                log_event(
                    LOGGER,
                    logging.WARNING,
                    "github_attempt_failed",
                    method=method,
                    path=path,
                    attempt=attempt,
                    error=type(exc).__name__,
                )
                if attempt < HTTP_MAX_RETRIES:
                    await self.sleep(RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
        if last_error:
            raise last_error
        raise RuntimeError(f"GitHub request failed after {HTTP_MAX_RETRIES} attempts")

    async def _get(self, path):
        return await self._request("GET", path)

    async def _post(self, path, body):
        return await self._request("POST", path, body)

    async def get_issue(self, n: int) -> dict:
        d = await self._get(f"/repos/{self.repo}/issues/{n}")
        return {
            "number": d["number"],
            "title": d["title"],
            "body": d.get("body") or "",
            "labels": [label["name"] for label in d.get("labels", [])],
        }

    async def open_issues(self, label: str = "auto-fix") -> list[dict]:
        d = await self._get(f"/repos/{self.repo}/issues?state=open&labels={label}")
        return [
            {"number": i["number"], "title": i["title"], "body": i.get("body") or ""} for i in d
        ]

    async def create_pr(self, title: str, head: str, body: str, base="main") -> dict:
        return await self._post(
            f"/repos/{self.repo}/pulls", {"title": title, "head": head, "base": base, "body": body}
        )

    async def comment(self, n: int, body: str):
        return await self._post(f"/repos/{self.repo}/issues/{n}/comments", {"body": body})

    async def workflow_runs(self, limit: int = 50) -> list[dict]:
        data = await self._get(f"/repos/{self.repo}/actions/runs?per_page={min(limit, 100)}")
        return [
            {
                "run_id": run["id"],
                "workflow": run.get("name") or "unknown",
                "status": run.get("status") or "unknown",
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url") or "",
                "branch": run.get("head_branch"),
                "event": run.get("event"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
            }
            for run in data.get("workflow_runs", [])
        ]
