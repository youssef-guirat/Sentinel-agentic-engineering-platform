"""Sentinel ops dashboard. Run: streamlit run dashboard/app.py"""

import asyncio
import os
import sqlite3

import pandas as pd
import streamlit as st

from config.settings import DB_PATH
from src.integrations.github_sync import sync_workflow_runs
from src.memory.store import MemoryStore

MemoryStore(DB_PATH)  # Apply schema migrations before the first dashboard query.

st.set_page_config(page_title="Sentinel Ops", layout="wide")
st.title("Sentinel — Agent Ops Dashboard")

with st.sidebar:
    st.header("GitHub synchronization")
    repository = st.text_input("Repository", value=os.getenv("SENTINEL_GITHUB_REPO", ""))
    if st.button("Sync workflow runs", disabled=not repository):
        try:
            count = asyncio.run(sync_workflow_runs(repository, MemoryStore(DB_PATH)))
            st.success(f"Synchronized {count} workflow run(s).")
            st.cache_data.clear()
        except Exception as exc:
            st.error(f"GitHub synchronization failed: {exc}")


@st.cache_data(ttl=15)
def load(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as db:
        return pd.read_sql(sql, db)


tasks = load("SELECT * FROM tasks ORDER BY ts DESC")
metrics = load("SELECT * FROM metrics ORDER BY ts")
workflow_runs = load("SELECT * FROM workflow_runs ORDER BY synced_ts DESC, run_id DESC")

# ---------- Row 1: North-star KPIs ----------
total = len(tasks)
ok = int(tasks.status.isin(["pr_created", "done_local"]).sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Issues processed", total)
c2.metric("Fix success rate", f"{ok / total:.0%}" if total else "–")
c3.metric("Escalated to human", int((tasks.status == "failed_after_self_heal").sum()))
c4.metric("Skipped (not bugs)", int((tasks.status == "skipped_non_bug").sum()))

# ---------- Row 2: outcome distribution + provider split ----------
col1, col2 = st.columns(2)
with col1:
    st.subheader("Task outcomes")
    st.bar_chart(tasks.status.value_counts())
with col2:
    st.subheader("Tokens per provider")
    if not metrics.empty:
        st.bar_chart(metrics.groupby("provider")[["input_tokens", "output_tokens"]].sum())
    else:
        st.info("Metrics appear after a model-backed run.")

# ---------- Row 3: token burn over time ----------
st.subheader("Cumulative input tokens over time (per provider)")
if not metrics.empty:
    m = metrics.copy()
    m["time"] = pd.to_datetime(m.ts, unit="s")
    piv = (
        m.pivot_table(index="time", columns="provider", values="input_tokens", aggfunc="sum")
        .fillna(0)
        .cumsum()
    )
    st.line_chart(piv)
else:
    st.info("No token history yet.")

# ---------- Row 4: efficiency + cache ----------
if not metrics.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total LLM requests", int(metrics.requests.sum()))
    c2.metric("Cached prefix tokens", int(metrics.cached_prefix.sum()))
    c3.metric("Response cache hits", int(metrics.cache_hits.sum()))

# ---------- Row 5: live ledger ----------
st.subheader("Recent task ledger")
show = tasks[["id", "issue", "status", "ts"]].copy()
show["ts"] = pd.to_datetime(show.ts, unit="s")
st.dataframe(show, use_container_width=True)

st.subheader("GitHub Actions runs")
if workflow_runs.empty:
    st.info("Enter owner/repository in the sidebar and synchronize workflow runs.")
else:
    st.dataframe(
        workflow_runs[
            ["workflow", "status", "conclusion", "branch", "event", "updated_at", "url"]
        ],
        use_container_width=True,
        hide_index=True,
    )

if st.button("Refresh now"):
    st.cache_data.clear()
    st.rerun()
