"""Database integration tests. Skipped unless TEST_DATABASE_URL points at a TimescaleDB you can wipe.

Local: docker compose -f db/docker-compose.db.yml up -d
       TEST_DATABASE_URL=postgresql://absorb:absorb@localhost:5433/absorb pytest api/tests/test_db.py
"""
import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg.types.json import Jsonb  # noqa: E402

from absorb_engine import MealItem, load_reference_data, score_meal  # noqa: E402
from pipeline.load_db import load  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")
LONDON = ZoneInfo("Europe/London")


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(URL, autocommit=False) as c:
        load(c)
        yield c


def test_reference_tables_loaded(conn):
    ref = load_reference_data()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM foods"); assert cur.fetchone()[0] == len(ref.foods)
        cur.execute("SELECT count(*) FROM absorption_modifiers WHERE human_verified"); assert cur.fetchone()[0] >= 1
        cur.execute("SELECT data->>'modifier_name' FROM absorption_modifiers WHERE modifier_id = 'ABS_MOD_IRON_001'")
        assert cur.fetchone()[0] == "Alternate_Day_Dosing"
        cur.execute("SELECT absorbed_target_mg_day FROM reference_intakes WHERE sex = 'female' AND age_min = 19")
        assert float(cur.fetchone()[0]) > 0


def test_reload_is_idempotent(conn):
    first = load(conn)
    second = load(conn)
    assert first == second


def test_hypertables_exist(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables")
        names = {r[0] for r in cur.fetchall()}
    assert {"meals", "meal_results", "agent_runs", "tool_calls", "chat_messages", "alerts"} <= names


def test_meal_round_trip_and_daily_rollup(conn):
    ref = load_reference_data()
    user = f"test|{uuid.uuid4()}"
    day = datetime(2026, 11, 8, tzinfo=LONDON)
    meals = [
        (day.replace(hour=8), [MealItem("11-788", 40), MealItem("12-313", 200)]),
        (day.replace(hour=13), [MealItem("13-658", 150), MealItem("17-165", 260)]),
        (day.replace(hour=23, minute=30), [MealItem("18-474", 150)]),          # still 8 Nov in London
        ((day + timedelta(days=1)).replace(hour=0, minute=30), [MealItem("14-327", 160)]),  # 9 Nov
    ]
    expected_day1 = 0.0
    with conn.cursor() as cur:
        cur.execute("INSERT INTO users (user_id, sex, birth_year, diet_type) VALUES (%s, 'female', 1996, 'omnivore')", (user,))
        for when, items in meals:
            mid = uuid.uuid4()
            r = score_meal(items, ref).to_dict()
            if when.date() == day.date():
                expected_day1 += r["absorbed_mg"]
            cur.execute("INSERT INTO meals (meal_id, user_id, eaten_at, items, source) VALUES (%s,%s,%s,%s,'manual')",
                        (mid, user, when, Jsonb([i.__dict__ for i in items])))
            cur.execute(
                """INSERT INTO meal_results (meal_id, eaten_at, user_id, iron_mg, absorbed_mg, potential_absorbed_mg,
                   fractional_pct, share_of_potential_pct, range_low_mg, range_high_mg, conflict_count, conflict_rule_ids,
                   contributions, conflicts, data_gaps, engine_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (mid, when, user, r["iron_mg"], r["absorbed_mg"], r["potential_absorbed_mg"], r["fractional_pct"],
                 r["share_of_potential_pct"], r["range_absorbed_mg"][0], r["range_absorbed_mg"][1], len(r["conflicts"]),
                 [c["rule_id"] for c in r["conflicts"]], Jsonb(r["contributions"]), Jsonb(r["conflicts"]),
                 Jsonb(r["data_gaps"]), r["engine_version"]))
        conn.commit()

        # Meals for days already materialised need a refresh (the API does this in save_meal / delete).
        from api.services import refresh_daily
        for when, _ in meals:
            refresh_daily(conn, when)
        cur = conn.cursor()
        cur.execute("SELECT day AT TIME ZONE 'Europe/London', meals, absorbed_mg, conflict_count FROM daily_iron "
                    "WHERE user_id = %s ORDER BY day", (user,))
        rows = cur.fetchall()
        assert [r[0].date().isoformat() for r in rows] == ["2026-11-08", "2026-11-09"]
        assert rows[0][1] == 3 and rows[1][1] == 1
        assert float(rows[0][2]) == pytest.approx(expected_day1, abs=0.001)
        assert rows[0][3] >= 1

        cur.execute("SELECT rule_id, count(*) FROM conflict_days WHERE user_id = %s GROUP BY rule_id", (user,))
        assert "RULE_IRON_002" in dict(cur.fetchall())

        cur.execute("DELETE FROM meal_results WHERE user_id = %s", (user,))
        cur.execute("DELETE FROM meals WHERE user_id = %s", (user,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user,))
        conn.commit()
