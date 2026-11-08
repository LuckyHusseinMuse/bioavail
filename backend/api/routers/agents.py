"""Agent endpoints. /agent/intake: photo or text -> matched, re-checked, scored draft for the user to confirm."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.agents.intake import analyse_meal
from api.agents.tools import ToolContext
from api.schemas import MealScoreIn
from api.auth import User, current_user
from api.db import get_conn
from api.runlog import RunLog
from api.services import ensure_user, ref, to_items
from api.settings import Settings, get_settings

router = APIRouter(tags=["agents"])
MAX_PHOTO_BYTES = 8 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def get_gemini(settings: Settings = Depends(get_settings)):
    if not settings.gemini_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Gemini is not configured (GEMINI_API_KEY)")
    from api.agents.gemini_client import GeminiClient

    return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model,
                        fallback_model=settings.gemini_fallback_model)


class _LoggedClient:
    """Wraps the Gemini client so every call is recorded in tool_calls."""

    def __init__(self, client, log: RunLog):
        self.client, self.log = client, log

    def generate(self, *, system, prompt, schema, image=None, mime_type="image/jpeg", temperature=0.2):
        step = "gemini.identify" if schema.__name__ == "IdentifyResult" else "gemini.review"
        with self.log.timed(step, {"schema": schema.__name__, "has_image": image is not None,
                                   "model": getattr(self.client, "model", None)}) as h:
            out = self.client.generate(system=system, prompt=prompt, schema=schema, image=image,
                                       mime_type=mime_type, temperature=temperature)
            h["summary"] = {"items": len(out.items),
                            "codes": [i.food_code for i in out.items],
                            "changes": getattr(out, "changes", None)}
            return out


@router.post("/agent/intake")
async def agent_intake(
    photo: UploadFile | None = File(None),
    text: str | None = Form(None),
    note: str | None = Form(None),
    user: User = Depends(current_user),
    conn: psycopg.Connection = Depends(get_conn),
    client=Depends(get_gemini),
):
    if photo is None and not (text and text.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Send a photo or a text description")
    image, mime = None, "image/jpeg"
    if photo is not None:
        mime = photo.content_type or "image/jpeg"
        if mime not in ALLOWED_TYPES:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported image type {mime}")
        image = await photo.read()
        if len(image) > MAX_PHOTO_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is larger than 8 MB")

    ensure_user(conn, user)
    log = RunLog(conn, user.user_id, "intake")
    try:
        out = analyse_meal(ref(), _LoggedClient(client, log), image=image, mime_type=mime, text=text, user_note=note)
    except Exception as e:
        log.finish("error", {"error": str(e)[:300]})
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Food recognition failed; try again or log manually") from e
    log.finish("needs_confirmation", {"items": len(out["items"]), "needs_attention": out["needs_attention"],
                                      "verdict": out["review"]["verdict"]})
    out["run_id"] = str(log.run_id)
    return out


# ----------------------------------------------------------------------------- analyst, fix, chat

def get_llm(settings: Settings = Depends(get_settings)):
    if not settings.gemini_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Gemini is not configured (GEMINI_API_KEY)")
    from api.agents.llm import GeminiChat

    return GeminiChat(api_key=settings.gemini_api_key, model=settings.gemini_model,
                      fallback_model=settings.gemini_fallback_model)


class _LoggedLLM:
    """Records each structured Gemini call (analyst, fix wording) in tool_calls."""

    def __init__(self, llm, log: RunLog, name: str):
        self.llm, self.log, self.name = llm, log, name
        self.model = getattr(llm, "model", None)

    def structured(self, *, system, prompt, schema, temperature=0.2):
        with self.log.timed(self.name, {"schema": schema.__name__, "model": self.model}) as h:
            out = self.llm.structured(system=system, prompt=prompt, schema=schema, temperature=temperature)
            h["summary"] = {"schema": schema.__name__}
            return out

    def step(self, **kw):
        return self.llm.step(**kw)


@router.post("/agent/analyse")
def agent_analyse(body: MealScoreIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn),
                  llm=Depends(get_llm)):
    from api.agents.analyst import analyse

    log = RunLog(conn, user.user_id, "analyst")
    ctx = ToolContext(user=user, conn=conn, log=log)
    out = analyse(ref(), _LoggedLLM(llm, log, "gemini.explain"), to_items(body.items), ctx)
    log.finish("ok", {"source": out["source"], "unsupported_numbers": out["unsupported_numbers"]})
    return {**out, "run_id": str(log.run_id)}


@router.post("/agent/fix")
def agent_fix(body: MealScoreIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn),
              llm=Depends(get_llm)):
    from api.agents.fix import fix

    profile = ensure_user(conn, user)
    log = RunLog(conn, user.user_id, "fix")
    out = fix(ref(), _LoggedLLM(llm, log, "gemini.word_fixes"), to_items(body.items), profile.get("diet_type"))
    log.finish("ok", {"source": out["source"], "fixes": len(out["fixes"])})
    return {**out, "run_id": str(log.run_id)}
