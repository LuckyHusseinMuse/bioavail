"""Seed a realistic demo week for one account (ProjectDefinition.md section 15, 'pre-loaded week of meals').

The week tells the demo story: a vegetarian who has tea with lunch most days. It produces conflict alerts,
evening shortfalls, and a weekly pattern alert ("Tea with lunch 6 times this week").
Re-running replaces the previous seed data for that account only (meals with source='seed' and their alerts).

Run:
  python -m pipeline.seed_demo --user "auth0|<the demo account's sub>"           # uses DATABASE_URL (Tiger Data)
  python -m pipeline.seed_demo --user "auth0|demo" --db postgresql://absorb:absorb@localhost:5433/absorb
The account's sub is shown by GET /me/profile (user_id) after logging in once.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "engine"))

LONDON = ZoneInfo("Europe/London")

# (days_ago, hour, minute, items). Today (0) only has breakfast, so the demo can log lunch live.
WEEK = [
    (6, 8, 0, [("11-788", 40), ("12-313", 200), ("17-833", 190, 0)]),
    (6, 13, 0, [("15-761", 300), ("11-862", 180), ("17-165", 260, 0)]),
    (6, 19, 0, [("13-670", 120), ("11-869", 180), ("13-524", 80)]),
    (5, 8, 0, [("11-773", 38), ("12-313", 150), ("14-329", 150)]),
    (5, 13, 0, [("11-981", 72), ("12-346", 30), ("13-517", 80), ("17-169", 260, 0)]),
    (5, 19, 0, [("15-761", 300), ("11-459", 55), ("12-184", 125)]),
    (4, 8, 0, [("11-788", 40), ("12-313", 200), ("17-833", 190, 0)]),
    (4, 13, 0, [("15-761", 300), ("11-862", 180), ("17-165", 260, 0)]),
    (4, 19, 0, [("13-660", 120), ("11-862", 180), ("13-530", 100), ("13-503", 80)]),
    (3, 8, 0, [("11-781", 50), ("12-313", 150), ("14-327", 160)]),
    (3, 13, 0, [("13-662", 120), ("11-981", 72), ("13-572", 30), ("17-165", 260, 0)]),
    (3, 19, 0, [("12-940", 100), ("11-450", 180), ("13-530", 100), ("13-573", 90)]),
    (2, 8, 0, [("11-788", 40), ("12-313", 200), ("17-833", 190, 0)]),
    (2, 13, 0, [("15-761", 300), ("11-862", 180), ("17-165", 260, 0)]),
    (2, 19, 0, [("13-570", 150), ("11-862", 180), ("13-503", 80), ("13-524", 80)]),
    (1, 8, 0, [("11-773", 38), ("12-313", 150), ("17-169", 260, 0)]),
    (1, 13, 0, [("13-532", 200), ("11-981", 72), ("17-165", 260, 0)]),
    (1, 19, 0, [("15-761", 300), ("11-862", 180), ("14-277", 15)]),
    (0, 8, 0, [("11-788", 40), ("12-313", 200), ("14-324", 80)]),
]


def seed(conn, user_id: str, profile: dict | None = None) -> dict:
    from api.alerts import rules
    from api.auth import User
    from api.schemas import MealItemIn
    from api.services import ensure_user, save_meal, to_items

    user = User(user_id)
    ensure_user(conn, user)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alerts WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM meal_results r USING meals m WHERE r.meal_id = m.meal_id AND r.eaten_at = m.eaten_at "
                    "AND m.user_id = %s AND m.source = 'seed'", (user_id,))
        cur.execute("DELETE FROM meals WHERE user_id = %s AND source = 'seed' RETURNING eaten_at", (user_id,))
        removed_days = {r["eaten_at"] for r in cur.fetchall()}
        p = profile or {"sex": "female", "birth_year": 1998, "diet_type": "vegetarian"}
        cur.execute("UPDATE users SET sex = %s, birth_year = %s, diet_type = %s WHERE user_id = %s",
                    (p["sex"], p["birth_year"], p["diet_type"], user_id))
        cur.execute("UPDATE alert_preferences SET daily_limit = 3, enabled = true WHERE user_id = %s", (user_id,))
    conn.commit()
    from api.services import refresh_daily
    for when in removed_days:                       # clear old seed totals from daily_iron
        refresh_daily(conn, when)

    today = datetime.now(LONDON).replace(hour=0, minute=0, second=0, microsecond=0)
    counts = {"meals": 0, "alerts": 0}
    days_seen = set()
    for days_ago, h, m, raw in WEEK:
        when = (today - timedelta(days=days_ago)).replace(hour=h, minute=m)
        items_in = [MealItemIn(food_code=r[0], grams=r[1], offset_min=r[2] if len(r) > 2 else 0) for r in raw]
        items = to_items(items_in)
        saved = save_meal(conn, user, items, when, "seed", "demo week", None)
        counts["meals"] += 1
        counts["alerts"] += len(rules.after_meal(conn, user, saved["meal_id"], items, saved["result"],
                                                 now=when + timedelta(minutes=2)))
        days_seen.add(days_ago)
    for d in sorted(days_seen, reverse=True):
        if d > 0:
            evening = (today - timedelta(days=d)).replace(hour=18, minute=30)
            counts["alerts"] += 1 if rules.shortfall(conn, user, now=evening) else 0
    counts["alerts"] += len(rules.weekly_patterns(conn, user, now=datetime.now(timezone.utc)))
    # Past alerts count as delivered and read except the latest few, so the notification centre looks lived-in.
    with conn.cursor() as cur:
        cur.execute("UPDATE alerts SET sent_at = scheduled_for WHERE user_id = %s AND scheduled_for <= now()", (user_id,))
        cur.execute("""UPDATE alerts SET read_at = scheduled_for + interval '5 minutes'
                       WHERE user_id = %s AND type <> 'weekly_pattern' AND scheduled_for < now() - interval '1 day'""",
                    (user_id,))
    conn.commit()
    return counts


def main() -> None:
    import psycopg
    from dotenv import load_dotenv
    from psycopg.rows import dict_row

    load_dotenv(BACKEND / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True, help="Auth0 sub of the demo account, e.g. auth0|abc123")
    ap.add_argument("--db", default=os.environ.get("DATABASE_URL"), help="Defaults to DATABASE_URL in backend/.env")
    a = ap.parse_args()
    if not a.db:
        sys.exit("No database: set DATABASE_URL or pass --db")
    with psycopg.connect(a.db, row_factory=dict_row) as conn:
        counts = seed(conn, a.user)
        with conn.cursor() as cur:
            cur.execute("SELECT type, count(*) AS n FROM alerts WHERE user_id = %s GROUP BY type ORDER BY type", (a.user,))
            by_type = {r["type"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT message FROM alerts WHERE user_id = %s AND type = 'weekly_pattern'", (a.user,))
            weekly = [r["message"] for r in cur.fetchall()]
    print(f"Seeded {counts['meals']} meals for {a.user}; alerts by type: {by_type}")
    for w in weekly:
        print("  weekly:", w)


if __name__ == "__main__":
    main()
