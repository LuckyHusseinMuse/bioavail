"""Person B's standalone dev server for the agents (Person A owns api/main.py).

From the repo root:
    api\\.venv\\Scripts\\activate          (Windows)   |  source api/.venv/bin/activate
    uvicorn api.dev_agents_app:app --reload --port 8000

Then set API_BASE_URL=http://localhost:8000 in web/.env.local. Note that this app only serves the
agent endpoints plus a few mock engine routes; /meals, /me/* and /alerts/* come from Person A.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load api/.env without adding a dependency.
_env = Path(__file__).with_name(".env")
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

from api.agents.registry import IMPL  # noqa: E402
from api.routers import agents  # noqa: E402

app = FastAPI(title="Absorb agents (dev)")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
app.include_router(agents.router)


# Minimal engine routes so the web app works against this server before Person A's API exists.
@app.get("/foods")
def foods(q: str = ""):
    return IMPL.search_foods(q) if q else IMPL.FOODS[:12] if hasattr(IMPL, "FOODS") else []


@app.get("/evidence/{entity_id}")
def evidence(entity_id: str):
    return IMPL.get_evidence(entity_id)


@app.get("/health")
def health():
    from api.agents import framework
    return {"ok": True, "tools": IMPL.__name__, "gemini": framework.gemini_available(), "model": framework.DEFAULT_MODEL}
