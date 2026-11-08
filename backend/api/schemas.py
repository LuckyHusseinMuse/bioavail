"""Request bodies. Responses are the engine's dicts (see ProjectDefinition.md section 11)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MealItemIn(BaseModel):
    food_code: str = Field(examples=["13-658"])
    grams: float = Field(gt=0, le=3000, examples=[150])
    offset_min: float = Field(0, ge=-720, le=720, description="Drinks: minutes after the meal starts (negative = before)")


class MealScoreIn(BaseModel):
    items: list[MealItemIn] = Field(min_length=1, max_length=40)


class MealIn(MealScoreIn):
    eaten_at: datetime | None = Field(None, description="Defaults to now")
    source: Literal["photo", "text", "manual"] = "manual"
    note: str | None = Field(None, max_length=500)
    intake: dict | None = Field(None, description="Intake agent output kept for audit (optional)")


class ChangeIn(BaseModel):
    kind: Literal["add", "remove", "swap", "retime", "regrams"]
    food_code: str = Field(description="Item to change, or the food to add")
    grams: float | None = Field(None, gt=0, le=3000)
    offset_min: float | None = Field(None, ge=-720, le=720)
    to_food_code: str | None = Field(None, description="For swap")


class SimulateIn(MealScoreIn):
    change: ChangeIn


class FixesIn(MealScoreIn):
    diet: str | None = None
    exclude: list[str] = Field(default_factory=list)
    top_n: int = Field(3, ge=1, le=10)


class ProfileIn(BaseModel):
    sex: Literal["male", "female"] | None = None
    birth_year: int | None = Field(None, ge=1900, le=2010)
    diet_type: Literal["omnivore", "vegetarian", "vegan", "pescatarian"] | None = None
    preferences: dict | None = None
    timezone: str | None = None
