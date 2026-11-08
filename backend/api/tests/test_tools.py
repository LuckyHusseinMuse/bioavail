"""Agent tool tests: behaviour, guardrails, logging, Gemini declarations and the HTTP route."""
import uuid
from datetime import datetime, timedelta

import pytest

from api.agents.tools import TOOLS, ToolContext, call_tool, gemini_tools, tool_schemas
from api.auth import User
from api.services import LONDON
from api.tests.helpers import TEST_DB, auth, needs_db

CURRY_TEA = [{"food_code": "15-761", "grams": 300}, {"food_code": "17-165", "grams": 260, "offset_min": 0}]


def ctx(conn=None, user="auth0|tool-test"):
    return ToolContext(user=User(user), conn=conn)


# ------------------------------------------------------------------ engine tools (no database)

def test_search_and_get_food():
    res = call_tool(ctx(), "search_foods", {"query": "lentil"})["results"]
    assert any(r["food_code"] == "13-658" for r in res)
    food = call_tool(ctx(), "get_food", {"food_code": "13-658"})
    assert food["phytate_mg_per_100g"] > 0
    assert "error" in call_tool(ctx(), "get_food", {"food_code": "99-999"})


def test_score_meal_numbers_come_from_engine():
    from absorb_engine import MealItem, load_reference_data, score_meal
    out = call_tool(ctx(), "score_meal", {"items": CURRY_TEA})
    direct = score_meal([MealItem("15-761", 300), MealItem("17-165", 260, 0)], load_reference_data()).to_dict()
    assert out["absorbed_mg"] == direct["absorbed_mg"]
    assert out["conflicts"][0]["evidence_id"]


def test_simulate_and_fixes():
    sim = call_tool(ctx(), "simulate_change", {"items": CURRY_TEA,
                                               "change": {"kind": "retime", "food_code": "17-165", "offset_min": 60}})
    assert sim["gain_mg"] > 0
    fixes = call_tool(ctx(), "suggest_fixes", {"items": CURRY_TEA})
    assert fixes["fixes"] and fixes["fixes"][0]["gain_mg"] > 0


def test_rules_and_evidence():
    rules = call_tool(ctx(), "get_rules", {"conflict_group": "IRON_POLYPHENOL_BEVERAGE"})["rules"]
    assert {r["rule_id"] for r in rules} >= {"RULE_IRON_002", "RULE_IRON_003", "RULE_IRON_006"}
    ev = call_tool(ctx(), "get_evidence", {"entity_id": "RULE_IRON_002"})
    assert any(e["paper"] and e["paper"]["year"] == "1999" for e in ev["evidence"])
    assert call_tool(ctx(), "get_evidence", {"entity_id": "ASSUME_015"})["kind"] == "assumption"
    assert "error" in call_tool(ctx(), "get_evidence", {"entity_id": "MADE_UP"})


def test_invalid_args_and_unknown_tool_return_errors():
    assert call_tool(ctx(), "score_meal", {"items": []})["error"] == "Invalid arguments"
    assert "error" in call_tool(ctx(), "score_meal", {"items": [{"food_code": "99-999", "grams": 10}]})
    assert "error" in call_tool(ctx(), "delete_everything", {})


def test_propose_tools_do_not_save():
    out = call_tool(ctx(), "propose_save_meal", {"items": CURRY_TEA, "note": "lunch"})
    assert out["status"] == "awaiting_user_approval" and out["preview"]["absorbed_mg"] > 0
    alert = call_tool(ctx(), "propose_alert", {"remind_at": "2026-11-08T15:00:00+00:00", "message": "Tea time"})
    assert alert["status"] == "awaiting_user_approval"


def test_db_tools_without_db_fail_cleanly():
    assert "error" in call_tool(ctx(), "get_daily_summary", {})


def test_no_tool_accepts_a_user_id():
    for s in tool_schemas():
        props = s["parameters"].get("properties", {})
        assert not ({"user", "user_id", "sub", "auth0_id"} & set(props)), s["name"]


def test_gemini_declarations_build():
    t = gemini_tools()
    names = {f.name for f in t.function_declarations}
    assert names == set(TOOLS)
    assert all("$ref" not in str(s["parameters"]) for s in tool_schemas())


# ------------------------------------------------------------------ database tools

@pytest.fixture
def db_user():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from psycopg.rows import dict_row

    from api.services import save_meal, to_items
    from api.schemas import MealItemIn

    user = User(f"auth0|tools-{uuid.uuid4()}")
    conn = psycopg.connect(TEST_DB, row_factory=dict_row)
    now = datetime.now(LONDON).replace(hour=13, minute=0, second=0, microsecond=0)
    for d in range(1, 5):                                          # tea with lunch on the 4 previous days
        save_meal(conn, user, to_items([MealItemIn(**i) for i in CURRY_TEA]), now - timedelta(days=d), "manual", None, None)
    save_meal(conn, user, to_items([MealItemIn(food_code="18-474", grams=150)]), now.replace(hour=19) - timedelta(days=1),
              "manual", None, None)
    yield conn, user
    with conn.cursor() as cur:
        for t in ("meal_results", "meals", "tool_calls", "agent_runs"):
            cur.execute(f"DELETE FROM {t} WHERE user_id = %s", (user.user_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user.user_id,))
    conn.commit()
    conn.close()


@needs_db
def test_history_patterns_and_daily(db_user):
    conn, user = db_user
    c = ToolContext(user=user, conn=conn)
    hist = call_tool(c, "get_meal_history", {"days": 7})
    assert len(hist["meals"]) == 5 and hist["meals"][0]["items"][0]["name"]
    pat = call_tool(c, "get_patterns", {"days": 7})
    top = pat["recurring_conflicts"][0]
    assert (top["rule_id"], top["slot"], top["times"]) == ("RULE_IRON_002", "lunch", 4)
    assert top["lost_mg"] > 0
    yesterday = (datetime.now(LONDON) - timedelta(days=1)).date().isoformat()
    day = call_tool(c, "get_daily_summary", {"date": yesterday})
    assert day["totals"]["meals"] == 2          # lunch with tea + steak dinner


@needs_db
def test_user_cannot_be_spoofed_and_calls_are_logged(db_user):
    from api.runlog import RunLog
    conn, user = db_user
    log = RunLog(conn, user.user_id, "test")
    c = ToolContext(user=user, conn=conn, log=log)
    out = call_tool(c, "get_meal_history", {"days": 7, "user_id": "auth0|someone-else"})
    assert len(out["meals"]) == 5                      # still the signed-in user's own meals
    call_tool(c, "get_food", {"food_code": "nope"})    # a failing call is logged too
    with conn.cursor() as cur:
        cur.execute("SELECT tool, ok, args FROM tool_calls WHERE run_id = %s ORDER BY called_at", (log.run_id,))
        rows = cur.fetchall()
    assert [(r["tool"], r["ok"]) for r in rows] == [("get_meal_history", True), ("get_food", False)]
    assert "user_id" not in rows[0]["args"]


@needs_db
def test_tools_over_http(client):
    h = auth(f"auth0|http-{uuid.uuid4()}")
    assert {t["name"] for t in client.get("/tools").json()["tools"]} == set(TOOLS)
    r = client.post("/tools/score_meal", headers=h, json={"items": CURRY_TEA})
    assert r.status_code == 200 and r.json()["result"]["absorbed_mg"] > 0
    assert client.post("/tools/score_meal", json={"items": CURRY_TEA}).status_code == 401
    assert client.post("/tools/nope", headers=h, json={}).status_code == 404
    for name in TOOLS:
        assert client.post(f"/tools/{name}", headers=h, json={}).status_code == 200   # bad args -> error result, not 500
