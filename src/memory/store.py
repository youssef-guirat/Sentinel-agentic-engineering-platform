"""Versioned SQLite persistence for memories, tasks, metrics, and workflow runs."""

from __future__ import annotations

import ctypes
import os
import sqlite3
import time
import uuid
from pathlib import Path

from config.settings import DB_PATH

SCHEMA_VERSION = 4


class MemoryStore:
    def __init__(self, path: str = DB_PATH):
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.db.executescript("""
            BEGIN;
            CREATE TABLE IF NOT EXISTS memories(
                id INTEGER PRIMARY KEY, agent TEXT, kind TEXT, content TEXT, ts REAL);
            CREATE TABLE IF NOT EXISTS tasks(
                id TEXT PRIMARY KEY, issue TEXT, status TEXT, result TEXT, ts REAL);
            PRAGMA user_version=1;
            COMMIT;
            """)
            version = 1
        if version < 2:
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(tasks)")}
            additions = {
                "issue_key": "TEXT",
                "correlation_id": "TEXT",
                "updated_ts": "REAL",
            }
            statements = ["BEGIN;"]
            for name, kind in additions.items():
                if name not in columns:
                    statements.append(f"ALTER TABLE tasks ADD COLUMN {name} {kind};")
            statements.append("UPDATE tasks SET updated_ts=COALESCE(updated_ts, ts);")
            statements.append("""
            CREATE TABLE IF NOT EXISTS issue_claims(
                issue_key TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_ts REAL NOT NULL);
            PRAGMA user_version=2;
            COMMIT;
            """)
            self.db.executescript("\n".join(statements))
            version = 2
        if version < 3:
            self.db.executescript("""
            BEGIN;
            CREATE TABLE IF NOT EXISTS metrics(
                id INTEGER PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                task_type TEXT NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cached_prefix INTEGER NOT NULL DEFAULT 0,
                cache_hits INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                ts REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS workflow_runs(
                run_id INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                workflow TEXT NOT NULL,
                status TEXT NOT NULL,
                conclusion TEXT,
                url TEXT NOT NULL,
                branch TEXT,
                event TEXT,
                created_at TEXT,
                updated_at TEXT,
                synced_ts REAL NOT NULL);
            PRAGMA user_version=3;
            COMMIT;
            """)
            version = 3
        if version < 4:
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(tasks)")}
            if "owner_pid" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN owner_pid INTEGER")
            self.db.execute("PRAGMA user_version=4")

    @property
    def schema_version(self) -> int:
        return self.db.execute("PRAGMA user_version").fetchone()[0]

    def add(self, agent: str, kind: str, content: str) -> None:
        self.db.execute(
            "INSERT INTO memories(agent,kind,content,ts) VALUES(?,?,?,?)",
            (agent, kind, content, time.time()),
        )

    def recent(self, agent: str, n: int = 100) -> list[tuple]:
        return self.db.execute(
            "SELECT content FROM memories WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, n)
        ).fetchall()

    def count(self, agent: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM memories WHERE agent=?", (agent,)).fetchone()[
            0
        ]

    def replace_all(self, agent: str, summary: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM memories WHERE agent=?", (agent,))
            self.db.execute(
                "INSERT INTO memories(agent,kind,content,ts) VALUES(?,?,?,?)",
                (agent, "consolidated", summary, time.time()),
            )

    def claim_task(self, issue_key: str, issue: str, correlation_id: str) -> str | None:
        """Atomically claim an issue once across processes and restarts."""
        task_id = uuid.uuid4().hex[:12]
        now = time.time()
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                "INSERT INTO issue_claims(issue_key,task_id,status,updated_ts) VALUES(?,?,?,?)",
                (issue_key, task_id, "running", now),
            )
            self.db.execute(
                "INSERT INTO tasks(id,issue,status,result,ts,issue_key,correlation_id,updated_ts,"
                "owner_pid) VALUES(?,?,?,NULL,?,?,?,?,?)",
                (task_id, issue, "running", now, issue_key, correlation_id, now, os.getpid()),
            )
            self.db.execute("COMMIT")
            return task_id
        except sqlite3.IntegrityError:
            self.db.execute("ROLLBACK")
            return None

    def new_task(self, issue: str) -> str:
        key = f"local:{uuid.uuid4().hex}"
        return self.claim_task(key, issue, uuid.uuid4().hex) or ""

    def release_claim(self, issue_key: str) -> bool:
        """Release a durable claim for an explicit operator-requested retry."""
        cursor = self.db.execute("DELETE FROM issue_claims WHERE issue_key=?", (issue_key,))
        return cursor.rowcount > 0

    def touch_task(self, task_id: str) -> None:
        now = time.time()
        with self.db:
            self.db.execute("UPDATE tasks SET updated_ts=? WHERE id=?", (now, task_id))
            self.db.execute(
                "UPDATE issue_claims SET updated_ts=? WHERE task_id=?", (now, task_id)
            )

    def finish_task(self, task_id: str, status: str, result: str) -> None:
        now = time.time()
        with self.db:
            self.db.execute(
                "UPDATE tasks SET status=?, result=?, updated_ts=? WHERE id=?",
                (status, result, now, task_id),
            )
            self.db.execute(
                "UPDATE issue_claims SET status=?, updated_ts=? WHERE task_id=?",
                (status, now, task_id),
            )

    def recover_interrupted(self) -> int:
        """Mark unfinished tasks interrupted and release their issue claims for retry."""
        rows = self.db.execute(
            "SELECT id, owner_pid FROM tasks WHERE status IN ('queued','running')"
        ).fetchall()
        task_ids = [row[0] for row in rows if not self._process_alive(row[1])]
        if not task_ids:
            return 0
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for task_id in task_ids:
                self.db.execute(
                    "UPDATE tasks SET status='interrupted', updated_ts=? WHERE id=?",
                    (now, task_id),
                )
                self.db.execute("DELETE FROM issue_claims WHERE task_id=?", (task_id,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return len(task_ids)

    @staticmethod
    def _process_alive(process_id: int | None) -> bool:
        if not process_id or process_id <= 0:
            return False
        if os.name == "nt":
            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                process_query_limited_information, False, process_id
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return True
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True

    def task(self, task_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def tasks(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, issue, status, substr(result,1,300) AS result, ts, issue_key, "
            "correlation_id, updated_ts, owner_pid FROM tasks ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def record_metric(self, **metric) -> None:
        self.db.execute(
            "INSERT INTO metrics(correlation_id,provider,model,task_type,requests,"
            "input_tokens,output_tokens,cached_prefix,cache_hits,status,ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                metric.get("correlation_id", "-"),
                metric["provider"],
                metric.get("model", ""),
                metric.get("task_type", "default"),
                metric.get("requests", 0),
                metric.get("input_tokens", 0),
                metric.get("output_tokens", 0),
                metric.get("cached_prefix", 0),
                metric.get("cache_hits", 0),
                metric.get("status", "success"),
                metric.get("ts", time.time()),
            ),
        )

    def upsert_workflow_runs(self, repo: str, runs: list[dict]) -> int:
        now = time.time()
        with self.db:
            for run in runs:
                self.db.execute(
                    "INSERT INTO workflow_runs(run_id,repo,workflow,status,conclusion,url,branch,"
                    "event,created_at,updated_at,synced_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,"
                    "conclusion=excluded.conclusion,updated_at=excluded.updated_at,"
                    "synced_ts=excluded.synced_ts",
                    (
                        run["run_id"],
                        repo,
                        run["workflow"],
                        run["status"],
                        run.get("conclusion"),
                        run["url"],
                        run.get("branch"),
                        run.get("event"),
                        run.get("created_at"),
                        run.get("updated_at"),
                        now,
                    ),
                )
        return len(runs)
