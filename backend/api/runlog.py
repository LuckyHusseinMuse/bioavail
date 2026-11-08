"""Log agent runs and tool calls to Tiger Data (agent_runs, tool_calls hypertables)."""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb


class RunLog:
    def __init__(self, conn: psycopg.Connection | None, user_id: str | None, agent: str):
        self.conn, self.user_id, self.agent = conn, user_id, agent
        self.run_id = uuid.uuid4()
        self.started = datetime.now(timezone.utc)
        self.outcome = "ok"
        self.detail: dict = {}
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO agent_runs (run_id, user_id, agent, started_at) VALUES (%s,%s,%s,%s)",
                            (self.run_id, user_id, agent, self.started))
            conn.commit()

    def tool(self, name: str, args: dict, result_summary: dict, ok: bool, duration_ms: int) -> None:
        if self.conn is None:
            return
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO tool_calls (run_id, called_at, user_id, tool, args, result_summary, ok, duration_ms) "
                        "VALUES (%s, now(), %s, %s, %s, %s, %s, %s)",
                        (self.run_id, self.user_id, name, Jsonb(args), Jsonb(result_summary), ok, duration_ms))
        self.conn.commit()

    @contextmanager
    def timed(self, name: str, args: dict):
        t0 = time.perf_counter()
        holder: dict = {}
        try:
            yield holder
            self.tool(name, args, holder.get("summary", {}), True, int((time.perf_counter() - t0) * 1000))
        except Exception as e:
            self.tool(name, args, {"error": str(e)[:300]}, False, int((time.perf_counter() - t0) * 1000))
            raise

    def finish(self, outcome: str | None = None, detail: dict | None = None) -> None:
        if self.conn is None:
            return
        with self.conn.cursor() as cur:
            cur.execute("UPDATE agent_runs SET finished_at = now(), outcome = %s, detail = %s "
                        "WHERE run_id = %s AND started_at = %s",
                        (outcome or self.outcome, Jsonb(detail or self.detail), self.run_id, self.started))
        self.conn.commit()
