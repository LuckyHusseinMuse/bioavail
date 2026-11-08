"""Chat endpoints. POST /chat streams Server-Sent Events; GET /chat/history returns stored messages.

SSE events (each line `data: {json}`):
  {"type": "tool", "name": "score_meal"}          the assistant is using a tool
  {"type": "message", "reply": ..., "proposals": [...], "unsupported_numbers": [...], "run_id": ...}
  {"type": "done"}
Send `?stream=false` to get the final message as plain JSON instead.
"""
from __future__ import annotations

import json
import queue
import threading
import uuid
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.agents.chat import run_chat
from api.agents.tools import ToolContext
from api.auth import User, current_user
from api import db
from api.db import get_conn
from api.routers.agents import get_llm
from api.runlog import RunLog
from api.services import ensure_user

router = APIRouter(tags=["chat"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def _history(conn: psycopg.Connection, user: User, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT message_id, sent_at, role, content, run_id FROM chat_messages WHERE user_id = %s "
                    "ORDER BY sent_at DESC LIMIT %s", (user.user_id, limit))
        rows = cur.fetchall()
    return [{**r, "message_id": str(r["message_id"]), "run_id": str(r["run_id"]) if r["run_id"] else None,
             "sent_at": r["sent_at"].isoformat()} for r in reversed(rows)]


def _store(conn: psycopg.Connection, user: User, role: str, content: str, run_id) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO chat_messages (message_id, user_id, sent_at, role, content, run_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (uuid.uuid4(), user.user_id, datetime.now(timezone.utc), role, content, run_id))
    conn.commit()


@router.get("/chat/history")
def chat_history(limit: int = Query(50, ge=1, le=200), user: User = Depends(current_user),
                 conn: psycopg.Connection = Depends(get_conn)):
    return {"messages": _history(conn, user, limit)}


@router.post("/chat")
def chat(body: ChatIn, stream: bool = True, user: User = Depends(current_user),
         conn: psycopg.Connection = Depends(get_conn), llm=Depends(get_llm)):
    ensure_user(conn, user)
    history = [{"role": "model" if m["role"] == "assistant" else m["role"], "content": m["content"]}
               for m in _history(conn, user, 24)]

    def run(c: psycopg.Connection, emit=None) -> dict:
        log = RunLog(c, user.user_id, "chat")
        _store(c, user, "user", body.message, log.run_id)
        out = run_chat(llm, ToolContext(user=user, conn=c, log=log), body.message, history, emit=emit)
        _store(c, user, "assistant", out["reply"], log.run_id)
        log.finish("ok", {"tools": out["tool_calls"], "unsupported_numbers": out["unsupported_numbers"],
                          "out_of_scope": out["out_of_scope"]})
        return {"type": "message", **out, "run_id": str(log.run_id)}

    if not stream:
        try:
            return run(conn)
        except Exception as e:
            from fastapi import HTTPException
            busy = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            raise HTTPException(503, "The assistant is busy right now (AI rate limit). Please try again in a minute."
                                if busy else "The assistant is unavailable right now. Please try again.") from e

    events: queue.Queue = queue.Queue()

    def worker():
        # Own pooled connection: the request's connection may be released before the stream ends.
        try:
            with db.pool().connection() as c:
                events.put(run(c, emit=lambda kind, data: events.put({"type": kind, **data})))
        except Exception:
            events.put({"type": "error", "detail": "The assistant is unavailable right now. Please try again."})
        events.put({"type": "done"})

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            ev = events.get()
            yield "data: " + json.dumps(ev, default=str) + "\n\n"
            if ev["type"] == "done":
                break

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
