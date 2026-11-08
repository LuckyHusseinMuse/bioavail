"""Signed-in user endpoints: profile, meals, daily view. The user always comes from the token."""
from __future__ import annotations

import uuid
from datetime import date, datetime

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Jsonb

from absorb_engine.daily import reference_for
from api.auth import User, current_user
from api.db import get_conn
from api.schemas import MealIn, ProfileIn
from api.services import (LONDON, daily_view, ensure_user, meals_between, profile_basis, ref, refresh_daily,
                          save_meal, to_items)

router = APIRouter(tags=["me"])


def _profile_out(row: dict) -> dict:
    sex, age, complete = profile_basis(row)
    out = {k: row[k] for k in ("user_id", "sex", "birth_year", "diet_type", "preferences", "timezone")}
    out["profile_complete"] = complete
    out["references"] = reference_for(ref(), sex, age)
    return out


@router.get("/me/profile")
def get_profile(user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    return _profile_out(ensure_user(conn, user))


@router.put("/me/profile")
def put_profile(body: ProfileIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    ensure_user(conn, user)
    fields = body.model_dump(exclude_unset=True)
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields) + ", updated_at = now()"
        vals = [Jsonb(v) if k == "preferences" else v for k, v in fields.items()]
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {sets} WHERE user_id = %s", (*vals, user.user_id))
        conn.commit()
    return _profile_out(ensure_user(conn, user))


@router.post("/meals", status_code=status.HTTP_201_CREATED)
def post_meal(body: MealIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    """Save a meal the user has approved. The server re-scores it; client numbers are never trusted."""
    ensure_user(conn, user)
    items = to_items(body.items)
    saved = save_meal(conn, user, items, body.eaten_at, body.source, body.note, body.intake)
    from api.alerts.rules import after_meal
    saved["alerts"] = after_meal(conn, user, saved["meal_id"], items, saved["result"])
    return saved


@router.get("/meals")
def list_meals(
    start: datetime | None = Query(None, alias="from"), end: datetime | None = Query(None, alias="to"),
    user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn),
):
    end = end or datetime.now(LONDON)
    start = start or datetime(end.year, end.month, end.day, tzinfo=LONDON)
    return {"meals": meals_between(conn, user, start, end)}


@router.get("/meals/{meal_id}")
def get_meal(meal_id: uuid.UUID, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("SELECT m.*, r.* FROM meals m JOIN meal_results r ON r.meal_id = m.meal_id AND r.eaten_at = m.eaten_at "
                    "WHERE m.meal_id = %s AND m.user_id = %s", (meal_id, user.user_id))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meal not found")
    return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in row.items()}


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(meal_id: uuid.UUID, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM meal_results WHERE meal_id = %s AND user_id = %s", (meal_id, user.user_id))
        cur.execute("DELETE FROM meals WHERE meal_id = %s AND user_id = %s RETURNING eaten_at", (meal_id, user.user_id))
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meal not found")
    refresh_daily(conn, row["eaten_at"])


@router.get("/me/daily")
def get_daily(day: date | None = Query(None, alias="date"), user: User = Depends(current_user),
              conn: psycopg.Connection = Depends(get_conn)):
    profile = ensure_user(conn, user)
    return daily_view(conn, user, day or datetime.now(LONDON).date(), profile)
