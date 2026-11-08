"""Person B endpoints: /agent/intake, /agent/analyse, /agent/fix, /chat, /chat/history.

Person A mounts this in api/main.py:
    from api.routers import agents
    app.include_router(agents.router)
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.agents import analyst, chat, fix, intake
from api.agents.framework import ToolContext, execute_tool
from api.agents.deps import current_user_id

router = APIRouter(tags=["agents"])


class Item(BaseModel):
    food_code: str
    name: str | None = None
    grams: float = Field(gt=0, le=3000)


class DrinkIn(Item):
    offset_min: int = Field(0, ge=-600, le=600)


class IntakeIn(BaseModel):
    text: str | None = Field(None, max_length=1000)
    image_base64: str | None = Field(None, max_length=8_000_000)  # ~6 MB image; the client resizes to 1024 px
    mime_type: Literal["image/jpeg", "image/png", "image/webp", "image/heic"] | None = None


class MealRef(BaseModel):
    """Either a saved meal_id or an inline meal."""
    meal_id: str | None = None
    items: list[Item] | None = None
    drinks: list[DrinkIn] | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


def _resolve(ref: MealRef, user_id: str) -> tuple[dict, dict | None]:
    if ref.meal_id:
        got = execute_tool("get_meal", {"meal_id": ref.meal_id}, ToolContext(user_id=user_id), {"get_meal"})
        if "error" in got:
            raise HTTPException(404, "meal not found")
        return got["meal"], got.get("result")
    if not ref.items:
        raise HTTPException(422, "give meal_id or items")
    return {"items": [i.model_dump() for i in ref.items], "drinks": [d.model_dump() for d in ref.drinks or []]}, None


@router.post("/agent/intake")
async def agent_intake(body: IntakeIn, user_id: str = Depends(current_user_id)):
    if not body.text and not body.image_base64:
        raise HTTPException(422, "send text or image_base64")
    try:
        return await run_in_threadpool(intake.run_intake, user_id=user_id, text=body.text,
                                       image_base64=body.image_base64, mime_type=body.mime_type)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@router.post("/agent/analyse")
async def agent_analyse(body: MealRef, user_id: str = Depends(current_user_id)):
    meal, result = _resolve(body, user_id)
    return await run_in_threadpool(analyst.run_analyst, user_id=user_id, meal=meal, result=result)


@router.post("/agent/fix")
async def agent_fix(body: MealRef, user_id: str = Depends(current_user_id)):
    meal, _ = _resolve(body, user_id)
    return await run_in_threadpool(fix.run_fix, user_id=user_id, meal=meal)


@router.post("/chat")
def chat_send(body: ChatIn, user_id: str = Depends(current_user_id)):
    # A sync generator: Starlette iterates it in a threadpool, so blocking Gemini calls are fine.
    return StreamingResponse(chat.sse(chat.stream_chat(user_id=user_id, message=body.message)),
                             media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/chat/history")
def chat_history(user_id: str = Depends(current_user_id)):
    return chat.get_history(user_id)
