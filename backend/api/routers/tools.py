"""Every agent tool as a plain HTTP call (PLAN.md done-when: 'every agent tool works from a plain HTTP call')."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Body, Depends, HTTPException, status

from api.agents.tools import TOOLS, ToolContext, call_tool, tool_schemas
from api.auth import User, current_user
from api.db import get_conn
from api.runlog import RunLog

router = APIRouter(tags=["tools"])


@router.get("/tools")
def list_tools():
    """Names, descriptions and JSON schemas (the same declarations Gemini receives)."""
    return {"tools": tool_schemas()}


@router.post("/tools/{name}")
def run_tool(name: str, args: dict = Body(default_factory=dict), user: User = Depends(current_user),
             conn: psycopg.Connection = Depends(get_conn)):
    if name not in TOOLS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tool {name}")
    log = RunLog(conn, user.user_id, "http")
    result = call_tool(ToolContext(user=user, conn=conn, log=log), name, args)
    log.finish("error" if "error" in result else "ok", {"tool": name})
    return {"run_id": str(log.run_id), "tool": name, "result": result}
