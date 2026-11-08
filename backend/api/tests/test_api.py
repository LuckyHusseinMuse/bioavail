"""API tests: public engine endpoints, auth, and (with TEST_DATABASE_URL) meals, profile and daily view."""
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from absorb_engine import MealItem, load_reference_data, score_meal
from api.agents.intake import IdentifyResult, ReviewResult
from api.routers.agents import get_gemini
from api.tests.helpers import auth, make_token, needs_db

REF = load_reference_data()
CURRY_TEA = {"items": [{"food_code": "15-761", "grams": 300}, {"food_code": "17-165", "grams": 260, "offset_min": 0}]}


# ------------------------------------------------------------------ public engine endpoints

def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["auth_mode"] == "auth0"
    assert h["data"]["unlinked_entities"] == [] and h["data"]["unresolved_papers"] == []


def test_food_search_and_lookup(client):
    res = client.get("/foods", params={"q": "red lentil"}).json()["results"]
    assert res[0]["food_code"] in ("13-658", "15-761")
    assert client.get("/foods/13-658").json()["phytate_mg_per_100g"] > 0
    assert client.get("/foods/99-999").status_code == 404
    drinks = client.get("/foods", params={"category": "drink", "limit": 100}).json()["results"]
    assert all(d["is_drink"] for d in drinks)


def test_score_matches_engine(client):
    out = client.post("/engine/score", json=CURRY_TEA).json()
    direct = score_meal([MealItem("15-761", 300), MealItem("17-165", 260, 0)], REF).to_dict()
    assert out["absorbed_mg"] == direct["absorbed_mg"]
    assert out["conflicts"][0]["rule_id"] == "RULE_IRON_002"


def test_score_rejects_bad_input(client):
    assert client.post("/engine/score", json={"items": [{"food_code": "99-999", "grams": 100}]}).status_code == 422
    assert client.post("/engine/score", json={"items": [{"food_code": "13-658", "grams": -1}]}).status_code == 422
    assert client.post("/engine/score", json={"items": []}).status_code == 422


def test_simulate_retime_tea(client):
    body = {**CURRY_TEA, "change": {"kind": "retime", "food_code": "17-165", "offset_min": 60}}
    out = client.post("/engine/simulate", json=body).json()
    assert out["gain_mg"] > 0
    assert not out["after"]["conflicts"] or all(c["rule_id"] != "RULE_IRON_002" for c in out["after"]["conflicts"])


def test_simulate_add_and_swap(client):
    add = client.post("/engine/simulate", json={**CURRY_TEA, "change": {"kind": "add", "food_code": "13-524"}}).json()
    assert any(i["food_code"] == "13-524" and i["grams"] == 80 for i in add["items_after"])
    swap = client.post("/engine/simulate", json={**CURRY_TEA, "change": {"kind": "swap", "food_code": "17-165",
                                                                          "to_food_code": "17-377"}}).json()
    assert swap["gain_mg"] > 0
    bad = client.post("/engine/simulate", json={**CURRY_TEA, "change": {"kind": "remove", "food_code": "13-524"}})
    assert bad.status_code == 422


def test_fixes(client):
    out = client.post("/engine/fixes", json={**CURRY_TEA, "diet": "vegan"}).json()
    assert out["fixes"] and out["fixes"][0]["gain_mg"] > 0


def test_interactions(client):
    static = client.get("/engine/interactions").json()
    assert len(static["nodes"]) == 7 and not any(e["active"] for e in static["edges"])
    live = client.post("/engine/interactions", json=CURRY_TEA).json()
    assert {e["id"]: e for e in live["edges"]}["polyphenols->nonhaem_iron"]["active"]


def test_evidence(client):
    rule = client.get("/evidence/RULE_IRON_002").json()
    assert rule["kind"] == "rule" and any(e["paper"] and "polyphenolic" in e["paper"]["title"] for e in rule["evidence"])
    assumption = client.get("/evidence/ASSUME_015").json()
    assert assumption["kind"] == "assumption"
    assert client.get("/evidence/IRON_013").json()["kind"] == "paper"
    assert client.get("/evidence/EVID_LINK_IRON_005").json()["paper"]["paper_id"] == "IRON_013"
    assert client.get("/evidence/NOPE").status_code == 404


def test_validation(client):
    v = client.get("/eval/validation").json()
    assert v["summary"]["held_out"]["n"] >= 5 and "rows" in v


# ------------------------------------------------------------------ auth (no database needed)

def test_me_requires_token(client):
    assert client.get("/me/profile").status_code == 401


@pytest.mark.parametrize("token", [
    make_token("u1", audience="https://wrong.example"),
    make_token("u1", issuer="https://evil.example/"),
    make_token("u1", expires_in=-10),
    make_token("u1", key=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    "not-a-jwt",
])
def test_bad_tokens_rejected(client, token):
    r = client.get("/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ------------------------------------------------------------------ database-backed

@needs_db
def test_profile_meals_daily_flow(client):
    user = f"auth0|test-{uuid.uuid4()}"
    h = auth(user)
    p = client.get("/me/profile", headers=h).json()
    assert p["user_id"] == user and not p["profile_complete"]
    p = client.put("/me/profile", headers=h, json={"sex": "female", "birth_year": 1998, "diet_type": "vegetarian"}).json()
    assert p["profile_complete"] and p["references"]["iron_rni_mg_day"] == 14.8

    # Client-sent numbers are ignored: the server re-scores.
    saved = client.post("/meals", headers=h, json={**CURRY_TEA, "eaten_at": "2026-11-08T13:00:00+00:00",
                                                    "source": "manual", "note": "test"}).json()
    meal_id = saved["meal_id"]
    expected = score_meal([MealItem("15-761", 300), MealItem("17-165", 260, 0)], REF).to_dict()["absorbed_mg"]
    assert saved["result"]["absorbed_mg"] == expected

    day = client.get("/me/daily", headers=h, params={"date": "2026-11-08"}).json()
    assert day["totals"]["meals"] == 1
    assert day["totals"]["absorbed_mg"] == pytest.approx(expected, abs=0.001)
    assert day["totals"]["conflict_count"] >= 1
    assert day["meals"][0]["meal_id"] == meal_id

    listed = client.get("/meals", headers=h, params={"from": "2026-11-08T00:00:00Z", "to": "2026-11-09T00:00:00Z"}).json()
    assert [m["meal_id"] for m in listed["meals"]] == [meal_id]
    assert client.get(f"/meals/{meal_id}", headers=h).status_code == 200

    # Another user cannot see or delete it.
    other = auth(f"auth0|other-{uuid.uuid4()}")
    assert client.get(f"/meals/{meal_id}", headers=other).status_code == 404
    assert client.delete(f"/meals/{meal_id}", headers=other).status_code == 404

    assert client.delete(f"/meals/{meal_id}", headers=h).status_code == 204
    assert client.get("/me/daily", headers=h, params={"date": "2026-11-08"}).json()["totals"]["meals"] == 0


class _FakeGemini:
    model = "fake"

    def __init__(self):
        self.n = 0

    def generate(self, *, system, prompt, schema, image=None, mime_type="image/jpeg", temperature=0.2):
        self.n += 1
        g = {"seen_as": "lentil curry", "food_code": "15-761", "grams": 300, "is_drink": False, "offset_min": 0,
             "confidence": 0.9, "portion_reasoning": "bowl", "match_reasoning": "dish in list"}
        tea = {**g, "seen_as": "black tea", "food_code": "17-165", "grams": 260, "is_drink": True}
        if schema is IdentifyResult:
            return IdentifyResult(items=[g], notes="")
        return ReviewResult(items=[g, tea], changes=["Added the mug of black tea"], verdict="corrected")


@needs_db
def test_intake_logs_run_and_tool_calls(client):
    from api import db

    app = client.app
    app.dependency_overrides[get_gemini] = lambda: _FakeGemini()
    try:
        user = f"auth0|intake-{uuid.uuid4()}"
        r = client.post("/agent/intake", headers=auth(user), files={"photo": ("meal.jpg", b"\xff\xd8fake", "image/jpeg")})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "needs_confirmation" and out["review"]["verdict"] == "corrected"
        assert "RULE_IRON_002" in [c["rule_id"] for c in out["score"]["conflicts"]]
        with db._pool.connection() as c, c.cursor() as cur:
            cur.execute("SELECT outcome FROM agent_runs WHERE run_id = %s", (out["run_id"],))
            assert cur.fetchone()["outcome"] == "needs_confirmation"
            cur.execute("SELECT tool, ok FROM tool_calls WHERE run_id = %s ORDER BY called_at", (out["run_id"],))
            assert [(t["tool"], t["ok"]) for t in cur.fetchall()] == [("gemini.identify", True), ("gemini.review", True)]
        bad = client.post("/agent/intake", headers=auth(user), files={"photo": ("x.gif", b"GIF8", "image/gif")})
        assert bad.status_code == 415
    finally:
        app.dependency_overrides.pop(get_gemini, None)


@needs_db
def test_intake_without_gemini_key_is_503(client):
    r = client.post("/agent/intake", headers=auth("auth0|x"), data={"text": "lentil curry"})
    assert r.status_code == 503
