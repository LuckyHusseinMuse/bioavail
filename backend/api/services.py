"""Shared logic for routers and agent tools: engine calls, meal persistence, user records."""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg
from fastapi import HTTPException, status
from psycopg.types.json import Jsonb

from absorb_engine import MealItem, ReferenceData, load_reference_data, score_meal
from absorb_engine.daily import reference_for
from api.auth import User
from api.schemas import ChangeIn, MealItemIn

LONDON = ZoneInfo("Europe/London")
DEFAULT_SEX, DEFAULT_AGE = "female", 30     # used when the profile is incomplete; flagged in responses


def ref() -> ReferenceData:
    return load_reference_data()


def to_items(items: list[MealItemIn]) -> list[MealItem]:
    r = ref()
    unknown = [i.food_code for i in items if i.food_code not in r.foods]
    if unknown:
        raise HTTPException(422, f"Unknown food codes: {unknown}")
    return [MealItem(i.food_code, i.grams, i.offset_min) for i in items]


def apply_change(items: list[MealItem], ch: ChangeIn) -> list[MealItem]:
    r = ref()
    if ch.food_code not in r.foods or (ch.to_food_code and ch.to_food_code not in r.foods):
        raise HTTPException(422, "Unknown food code in change")
    idx = next((i for i, it in enumerate(items) if it.food_code == ch.food_code), None)
    if ch.kind == "add":
        grams = ch.grams or r.foods[ch.food_code].serving_g
        return items + [MealItem(ch.food_code, grams, ch.offset_min or 0)]
    if idx is None:
        raise HTTPException(422, f"{ch.food_code} is not in the meal")
    it = items[idx]
    rest = items[:idx] + items[idx + 1:]
    if ch.kind == "remove":
        return rest
    if ch.kind == "swap":
        if not ch.to_food_code:
            raise HTTPException(422, "swap needs to_food_code")
        return rest + [MealItem(ch.to_food_code, ch.grams or it.grams, it.offset_min)]
    if ch.kind == "retime":
        if ch.offset_min is None:
            raise HTTPException(422, "retime needs offset_min")
        return rest + [replace(it, offset_min=ch.offset_min)]
    if ch.kind == "regrams":
        if ch.grams is None:
            raise HTTPException(422, "regrams needs grams")
        return rest + [replace(it, grams=ch.grams)]
    raise HTTPException(422, "Unknown change")


# ----------------------------------------------------------------------------- users

def ensure_user(conn: psycopg.Connection, user: User) -> dict:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user.user_id,))
        cur.execute("INSERT INTO alert_preferences (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user.user_id,))
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user.user_id,))
        row = cur.fetchone()
    conn.commit()
    return row


def profile_basis(profile: dict) -> tuple[str, int, bool]:
    """(sex, age, complete) for daily references."""
    sex = profile.get("sex")
    by = profile.get("birth_year")
    if sex and by:
        return sex, max(19, date.today().year - by), True
    return sex or DEFAULT_SEX, DEFAULT_AGE if not by else max(19, date.today().year - by), False


# ----------------------------------------------------------------------------- meals

def save_meal(conn: psycopg.Connection, user: User, items: list[MealItem], eaten_at: datetime | None,
              source: str, note: str | None, intake: dict | None) -> dict:
    when = eaten_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=LONDON)
    result = score_meal(items, ref()).to_dict()
    meal_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO meals (meal_id, user_id, eaten_at, items, source, note, intake) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (meal_id, user.user_id, when,
                     Jsonb([{"food_code": i.food_code, "grams": i.grams, "offset_min": i.offset_min} for i in items]),
                     source, note, Jsonb(intake) if intake else None))
        cur.execute(
            """INSERT INTO meal_results (meal_id, eaten_at, user_id, iron_mg, absorbed_mg, potential_absorbed_mg,
               fractional_pct, share_of_potential_pct, range_low_mg, range_high_mg, conflict_count, conflict_rule_ids,
               contributions, conflicts, data_gaps, engine_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (meal_id, when, user.user_id, result["iron_mg"], result["absorbed_mg"], result["potential_absorbed_mg"],
             result["fractional_pct"], result["share_of_potential_pct"], result["range_absorbed_mg"][0],
             result["range_absorbed_mg"][1], len(result["conflicts"]), [c["rule_id"] for c in result["conflicts"]],
             Jsonb(result["contributions"]), Jsonb(result["conflicts"]), Jsonb(result["data_gaps"]),
             result["engine_version"]))
    conn.commit()
    refresh_daily(conn, when)
    return {"meal_id": str(meal_id), "eaten_at": when.isoformat(), "result": result}


def refresh_daily(conn: psycopg.Connection, when: datetime, tz: str = "Europe/London") -> None:
    """Refresh one London day of the daily_iron continuous aggregate.

    Real-time aggregation only covers data newer than the last materialisation, so a meal logged for an
    earlier day (or deleted) would otherwise be missing from daily_iron until the next policy refresh.
    refresh_continuous_aggregate cannot run inside a transaction, hence autocommit.
    """
    local = when.astimezone(ZoneInfo(tz))
    start = datetime(local.year, local.month, local.day, tzinfo=ZoneInfo(tz))
    conn.commit()
    previous = conn.autocommit
    conn.autocommit = True
    try:
        conn.execute("CALL refresh_continuous_aggregate('daily_iron', %s::timestamptz, %s::timestamptz)",
                     (start, start + timedelta(days=1)))
    finally:
        conn.autocommit = previous


def day_bounds(day: date, tz: str = "Europe/London") -> tuple[datetime, datetime]:
    z = ZoneInfo(tz)
    start = datetime(day.year, day.month, day.day, tzinfo=z)
    return start, start + timedelta(days=1)


def meals_between(conn: psycopg.Connection, user: User, start: datetime, end: datetime) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT m.meal_id, m.eaten_at, m.items, m.source, m.note,
                      r.iron_mg, r.absorbed_mg, r.potential_absorbed_mg, r.fractional_pct, r.share_of_potential_pct,
                      r.conflicts, r.data_gaps, r.contributions, r.conflict_count
               FROM meals m JOIN meal_results r ON r.meal_id = m.meal_id AND r.eaten_at = m.eaten_at
               WHERE m.user_id = %s AND m.eaten_at >= %s AND m.eaten_at < %s
               ORDER BY m.eaten_at""",
            (user.user_id, start, end))
        rows = cur.fetchall()
    r_ = ref()
    for r in rows:
        r["meal_id"] = str(r["meal_id"])
        for k in ("iron_mg", "absorbed_mg", "potential_absorbed_mg", "fractional_pct", "share_of_potential_pct"):
            r[k] = None if r[k] is None else float(r[k])
        # Full engine result for the UI (deterministic, so it matches what was stored).
        items = [MealItem(i["food_code"], float(i["grams"]), float(i.get("offset_min", 0))) for i in r["items"]
                 if i["food_code"] in r_.foods]
        r["result"] = score_meal(items, r_).to_dict()
    return rows


def update_meal(conn: psycopg.Connection, user: User, meal_id: str, items: list[MealItem]) -> dict | None:
    """Replace a meal's items (e.g. after applying a fix) and re-score it. Keeps the meal id and time."""
    with conn.cursor() as cur:
        cur.execute("SELECT eaten_at FROM meals WHERE meal_id = %s AND user_id = %s", (meal_id, user.user_id))
        row = cur.fetchone()
        if row is None:
            return None
        when = row["eaten_at"]
        result = score_meal(items, ref()).to_dict()
        cur.execute("UPDATE meals SET items = %s WHERE meal_id = %s AND eaten_at = %s",
                    (Jsonb([{"food_code": i.food_code, "grams": i.grams, "offset_min": i.offset_min} for i in items]),
                     meal_id, when))
        cur.execute(
            """UPDATE meal_results SET iron_mg = %s, absorbed_mg = %s, potential_absorbed_mg = %s, fractional_pct = %s,
               share_of_potential_pct = %s, range_low_mg = %s, range_high_mg = %s, conflict_count = %s,
               conflict_rule_ids = %s, contributions = %s, conflicts = %s, data_gaps = %s, engine_version = %s
               WHERE meal_id = %s AND eaten_at = %s""",
            (result["iron_mg"], result["absorbed_mg"], result["potential_absorbed_mg"], result["fractional_pct"],
             result["share_of_potential_pct"], result["range_absorbed_mg"][0], result["range_absorbed_mg"][1],
             len(result["conflicts"]), [c["rule_id"] for c in result["conflicts"]], Jsonb(result["contributions"]),
             Jsonb(result["conflicts"]), Jsonb(result["data_gaps"]), result["engine_version"], meal_id, when))
    conn.commit()
    refresh_daily(conn, when)
    return {"meal_id": str(meal_id), "eaten_at": when.isoformat(), "result": result}


def daily_view(conn: psycopg.Connection, user: User, day: date, profile: dict) -> dict:
    sex, age, complete = profile_basis(profile)
    tz = profile.get("timezone") or "Europe/London"
    start, end = day_bounds(day, tz)
    with conn.cursor() as cur:
        # Totals from the TimescaleDB continuous aggregate (real-time, London days).
        cur.execute("SELECT meals, iron_mg, absorbed_mg, potential_absorbed_mg, conflict_count FROM daily_iron "
                    "WHERE user_id = %s AND day = %s", (user.user_id, start))
        agg = cur.fetchone() or {"meals": 0, "iron_mg": 0, "absorbed_mg": 0, "potential_absorbed_mg": 0, "conflict_count": 0}
    refs = reference_for(ref(), sex, age)
    iron = float(agg["iron_mg"] or 0)
    absorbed = float(agg["absorbed_mg"] or 0)
    potential = float(agg["potential_absorbed_mg"] or 0)
    return {
        "date": day.isoformat(),
        "profile_complete": complete,
        "meals": meals_between(conn, user, start, end),
        "totals": {
            "meals": int(agg["meals"] or 0), "iron_mg": round(iron, 2), "absorbed_mg": round(absorbed, 3),
            "potential_absorbed_mg": round(potential, 3), "inhibitors_cost_mg": round(potential - absorbed, 3),
            "share_of_potential_pct": round(100 * absorbed / potential) if potential else None,
            "conflict_count": int(agg["conflict_count"] or 0),
        },
        "references": refs,
        "progress": {
            "eaten_share_of_rni": round(iron / refs["iron_rni_mg_day"], 2),
            "absorbed_share_of_target": round(absorbed / refs["absorbed_target_mg_day"], 2),
        },
        "source": "daily_iron continuous aggregate",
    }
