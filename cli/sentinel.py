"""Sentinel CLI. Concepts: CLI, Headless Runs, Background Agents.
Usage:
  sentinel fix --issue 42 --repo owner/name
  sentinel watch --repo owner/name
  sentinel status
  sentinel eval [min_pass]
  sentinel meta
  sentinel mcp
"""

import asyncio
import json

import typer

app = typer.Typer(help="Sentinel — autonomous multi-agent code guardian")


def _build(repo: str):
    from src.integrations.github import GitHubClient
    from src.llm.provider import LLMRouter
    from src.memory.store import MemoryStore
    from src.orchestrator.orchestrator import SentinelOrchestrator

    store = MemoryStore()
    recovered = store.recover_interrupted()
    if recovered:
        typer.echo(f"Recovered {recovered} interrupted task(s).")
    router = LLMRouter(metric_recorder=store.record_metric)
    gh = GitHubClient(repo) if "/" in repo else None
    orch = SentinelOrchestrator(router, ".", store, gh)
    return router, orch, gh, store


@app.command()
def fix(
    issue: int = typer.Option(..., "--issue", help="GitHub issue number"),
    repo: str = typer.Option(".", "--repo", help="owner/repository or local mode"),
    force: bool = typer.Option(False, "--force", help="retry an already claimed issue"),
):
    """Fix one issue end-to-end (headless-friendly)."""

    async def _():
        from src.pipeline.background import BackgroundRunner

        router, orch, gh, store = _build(repo)
        data = (
            await gh.get_issue(issue)
            if gh
            else {"number": issue, "title": "local issue", "body": "", "labels": []}
        )
        runner = BackgroundRunner(orch, store, source=repo)
        task_id = runner.submit(data, force=force)
        if task_id is None:
            typer.secho("Issue was already claimed; refusing duplicate processing.", fg="yellow")
            return
        task = await runner.wait(task_id)
        print(task["result"] if task else json.dumps({"status": "missing_task"}))
        print("Usage:", router.stats())

    asyncio.run(_())


@app.command()
def watch(repo: str = "."):
    """Poll labeled issues and fix them in the background."""

    async def _():
        from src.pipeline.background import BackgroundRunner

        _router, orch, gh, store = _build(repo)
        if not gh:
            typer.secho("watch requires owner/repo", fg="red")
            return
        runner = BackgroundRunner(orch, store, source=repo)
        typer.echo("Watching… Ctrl+C to stop.")
        while True:
            for i in await gh.open_issues():
                tid = runner.submit(i)
                if tid:
                    typer.echo(f"submitted #{i['number']} -> task {tid}")
                else:
                    typer.echo(f"skipped duplicate issue #{i['number']}")
            await asyncio.sleep(60)
            await runner.wait_all()

    try:
        asyncio.run(_())
    except KeyboardInterrupt:
        pass


@app.command()
def status():
    """Show background task ledger."""
    from src.memory.store import MemoryStore

    for t in MemoryStore().tasks():
        typer.echo(f"{t['status']:>10}  {t['issue']}")


@app.command("sync-runs")
def sync_runs(
    repo: str = typer.Option(..., "--repo", help="GitHub owner/repository"),
    limit: int = typer.Option(50, "--limit", min=1, max=100),
):
    """Pull GitHub Actions run metadata into the local dashboard database."""

    async def _():
        from src.integrations.github_sync import sync_workflow_runs
        from src.memory.store import MemoryStore

        count = await sync_workflow_runs(repo, MemoryStore(), limit=limit)
        typer.echo(f"Synchronized {count} workflow run(s) for {repo}.")

    asyncio.run(_())


@app.command()
def eval(min_pass: float = 0.8):
    """Run the eval suite (CI gate)."""
    from evals.run_evals import main

    asyncio.run(main(min_pass))


@app.command()
def meta():
    """Run one meta-orchestrator cycle (agents managing agents)."""

    async def _():
        from src.llm.provider import LLMRouter
        from src.memory.store import MemoryStore
        from src.orchestrator.meta import MetaOrchestrator

        r = await MetaOrchestrator(LLMRouter(), MemoryStore(), ".").run_cycle()
        print(json.dumps(r, indent=2))

    asyncio.run(_())


@app.command()
def mcp():
    """Run the dev-tools MCP server."""
    from src.mcp.dev_tools_server import mcp as server

    server.run()


if __name__ == "__main__":
    app()
