"""Absorb API.

Run locally:  uvicorn api.main:app --reload --app-dir backend   (or from backend/: uvicorn api.main:app --reload)
Docs:         http://localhost:8000/docs
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND / "engine") not in sys.path:
    sys.path.insert(0, str(BACKEND / "engine"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from absorb_engine.loaders import unlinked_entities, unresolved_papers  # noqa: E402
from absorb_engine.model import ENGINE_VERSION  # noqa: E402
from api import db  # noqa: E402
from api.routers import agents, alerts, chat, engine, me, tools  # noqa: E402
from api.services import ref  # noqa: E402
from api.settings import get_settings  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ref()                                   # load and validate reference data at startup
    db.open_pool(settings.database_url)
    if settings.scheduler_enabled and settings.database_url:
        from api.alerts import scheduler
        scheduler.start()
    yield
    if settings.scheduler_enabled:
        from api.alerts import scheduler
        scheduler.stop()
    db.close_pool()


app = FastAPI(title="Absorb API", version=ENGINE_VERSION, lifespan=lifespan,
              description="Iron absorption engine, meals and agents. Every number comes from the engine.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", tags=["meta"])
def health():
    settings = get_settings()
    r = ref()
    db_ok = None
    if db._pool is not None:
        try:
            with db._pool.connection() as c, c.cursor() as cur:
                cur.execute("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False
    return {
        "status": "ok", "engine_version": ENGINE_VERSION, "auth_mode": settings.auth_mode,
        "database": db_ok, "gemini": bool(settings.gemini_api_key),
        "scheduler": settings.scheduler_enabled, "web_push": bool(settings.vapid_private_key),
        "data": {"foods": len(r.foods), "modifiers": len(r.modifiers), "rules": len(r.rules),
                 "unlinked_entities": unlinked_entities(r), "unresolved_papers": unresolved_papers(r)},
    }


app.include_router(engine.router)
app.include_router(me.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(chat.router)
app.include_router(alerts.router)
