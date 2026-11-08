"""Alert rules, preferences, notification centre, reminders and push dispatch (needs TEST_DATABASE_URL)."""
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from api.alerts import push, rules
from api.auth import User
from api.schemas import MealItemIn
from api.services import save_meal, to_items
from api.tests.helpers import TEST_DB, auth, needs_db

LONDON = ZoneInfo("Europe/London")
CURRY_TEA = [{"food_code": "15-761", "grams": 300}, {"food_code": "17-165", "grams": 260, "offset_min": 0}]


def test_quiet_hours_logic():
    q = (time(22, 0), time(7, 0))
    assert rules.in_quiet_hours(datetime(2026, 11, 8, 23, 30, tzinfo=LONDON), *q)
    assert rules.in_quiet_hours(datetime(2026, 11, 8, 6, 59, tzinfo=LONDON), *q)
    assert not rules.in_quiet_hours(datetime(2026, 11, 8, 12, 0, tzinfo=LONDON), *q)
    assert rules.quiet_end_after(datetime(2026, 11, 8, 23, 30, tzinfo=LONDON), time(7, 0)) == datetime(2026, 11, 9, 7, 0, tzinfo=LONDON)
    assert not rules.in_quiet_hours(datetime(2026, 11, 8, 23, 30, tzinfo=LONDON), None, None)


@pytest.fixture
def conn_user():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from psycopg.rows import dict_row
    user = User(f"auth0|alerts-{uuid.uuid4()}")
    conn = psycopg.connect(TEST_DB, row_factory=dict_row)
    rules.get_prefs(conn, user)
    yield conn, user
    with conn.cursor() as cur:
        for t in ("alerts", "meal_results", "meals", "tool_calls", "agent_runs", "chat_messages", "alert_preferences"):
            cur.execute(f"DELETE FROM {t} WHERE user_id = %s", (user.user_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user.user_id,))
    conn.commit()
    conn.close()


def _log(conn, user, items, when):
    meal_items = to_items([MealItemIn(**i) for i in items])
    saved = save_meal(conn, user, meal_items, when, "manual", None, None)
    return saved, meal_items


def _set(conn, user, **kw):
    sets = ", ".join(f"{k} = %s" for k in kw)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE alert_preferences SET {sets} WHERE user_id = %s", (*kw.values(), user.user_id))
    conn.commit()


@needs_db
def test_conflict_and_data_gap_alerts_with_dedupe(conn_user):
    conn, user = conn_user
    now = datetime(2026, 11, 8, 13, 5, tzinfo=LONDON)
    saved, items = _log(conn, user, CURRY_TEA + [{"food_code": "17-171", "grams": 260}], now)   # green tea: data gap
    created = rules.after_meal(conn, user, saved["meal_id"], items, saved["result"], now=now)
    types = [a["type"] for a in created]
    assert types == ["conflict", "data_gap"]
    conflict = created[0]
    assert conflict["source_rule_id"] == "RULE_IRON_002" and "Try: have the" in conflict["message"]
    assert conflict["data"]["fix_gain_mg"] > 0 and conflict["meal_id"] == saved["meal_id"]
    assert "Tea, green" in created[1]["message"]
    assert rules.after_meal(conn, user, saved["meal_id"], items, saved["result"], now=now) == []   # deduped


@needs_db
def test_daily_limit_disabled_types_and_master_switch(conn_user):
    conn, user = conn_user
    now = datetime(2026, 11, 8, 13, 0, tzinfo=LONDON)
    _set(conn, user, daily_limit=1)
    for k in range(2):
        s, items = _log(conn, user, CURRY_TEA, now + timedelta(minutes=k))
        out = rules.after_meal(conn, user, s["meal_id"], items, s["result"], now=now + timedelta(minutes=k))
        assert len(out) == (1 if k == 0 else 0)
    _set(conn, user, daily_limit=5, enabled_types=["data_gap"])
    s, items = _log(conn, user, CURRY_TEA, now + timedelta(minutes=5))
    assert rules.after_meal(conn, user, s["meal_id"], items, s["result"], now=now) == []
    _set(conn, user, enabled=False, enabled_types=list(rules.AUTOMATIC | {"timing"}))
    s, items = _log(conn, user, CURRY_TEA, now + timedelta(minutes=6))
    assert rules.after_meal(conn, user, s["meal_id"], items, s["result"], now=now) == []


@needs_db
def test_quiet_hours_hold_alert_until_they_end(conn_user):
    conn, user = conn_user
    _set(conn, user, quiet_start=time(22, 0), quiet_end=time(7, 0))
    late = datetime(2026, 11, 8, 23, 15, tzinfo=LONDON)
    s, items = _log(conn, user, CURRY_TEA, late)
    a = rules.after_meal(conn, user, s["meal_id"], items, s["result"], now=late)[0]
    assert datetime.fromisoformat(a["scheduled_for"]) == datetime(2026, 11, 9, 7, 0, tzinfo=LONDON)
    # Not delivered during quiet hours; delivered once they end.
    assert push.dispatch_due(conn, now=late + timedelta(hours=1), sender=lambda *_: "sent", user_id=user.user_id)["due"] == 0
    assert push.dispatch_due(conn, now=datetime(2026, 11, 9, 7, 1, tzinfo=LONDON), sender=lambda *_: "sent", user_id=user.user_id)["due"] == 1


@needs_db
def test_shortfall_only_in_evening_once_per_day(conn_user):
    conn, user = conn_user
    day = datetime(2026, 11, 3, tzinfo=LONDON)
    _log(conn, user, CURRY_TEA, day.replace(hour=13))
    _log(conn, user, [{"food_code": "11-788", "grams": 40}, {"food_code": "12-313", "grams": 200},
                      {"food_code": "17-833", "grams": 190}], day.replace(hour=8))
    assert rules.shortfall(conn, user, now=day.replace(hour=15)) is None          # too early
    a = rules.shortfall(conn, user, now=day.replace(hour=18, minute=30))
    assert a and a["type"] == "shortfall" and "blocked" in a["message"]
    assert rules.shortfall(conn, user, now=day.replace(hour=20)) is None          # once per day


@needs_db
def test_weekly_pattern_alert(conn_user):
    conn, user = conn_user
    now = datetime.now(LONDON)
    for d in range(1, 5):
        _log(conn, user, CURRY_TEA, (now - timedelta(days=d)).replace(hour=13, minute=0))
    created = rules.weekly_patterns(conn, user, now=now)
    assert len(created) == 1
    a = created[0]
    assert a["type"] == "weekly_pattern" and a["message"].startswith("Tea with lunch 4 times this week")
    assert rules.weekly_patterns(conn, user, now=now) == []                      # once per ISO week


@needs_db
def test_dispatch_pushes_and_drops_expired_subscriptions(conn_user):
    conn, user = conn_user
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
    from psycopg.types.json import Jsonb
    _set(conn, user, push_subscription=Jsonb(sub))
    now = datetime(2026, 11, 8, 15, 0, tzinfo=LONDON)
    rules.create_alert(conn, user, type="timing", message="You can have your tea now.", dedupe="t1",
                       now=now - timedelta(hours=1), scheduled_for=now)
    sent = []
    out = push.dispatch_due(conn, now=now, sender=lambda s, p: sent.append((s, p)) or "sent", user_id=user.user_id)
    assert out == {"due": 1, "pushed": 1, "in_app_only": 0, "gone": 0}
    assert sent[0][1]["body"] == "You can have your tea now."
    rules.create_alert(conn, user, type="timing", message="Again", dedupe="t2", now=now, scheduled_for=now)
    assert push.dispatch_due(conn, now=now, sender=lambda s, p: "gone", user_id=user.user_id)["gone"] == 1
    assert rules.get_prefs(conn, user)["push_subscription"] is None


@needs_db
def test_alert_endpoints(client):
    uid = f"auth0|alert-http-{uuid.uuid4()}"
    h = auth(uid)
    saved = client.post("/meals", headers=h, json={"items": CURRY_TEA, "source": "manual"}).json()
    assert [a["type"] for a in saved["alerts"]] == ["conflict"]

    listing = client.get("/alerts", headers=h).json()
    assert listing["unread"] == 1
    aid = listing["alerts"][0]["alert_id"]
    assert client.patch(f"/alerts/{aid}", headers=h, json={"read": True}).json()["read_at"]
    assert client.get("/alerts", headers=h, params={"unread_only": True}).json()["alerts"] == []
    assert client.patch(f"/alerts/{aid}", headers=auth("auth0|intruder"), json={"read": True}).status_code == 404

    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.post("/alerts", headers=h, json={"remind_at": future, "message": "Tea time: no lunch conflict now."})
    assert r.status_code == 201
    assert all(a["type"] != "timing" for a in client.get("/alerts", headers=h).json()["alerts"])   # not due yet
    assert client.post("/alerts", headers=h, json={"remind_at": "2026-11-08T15:00:00", "message": "x"}).status_code == 422

    p = client.put("/alerts/preferences", headers=h, json={"quiet_start": "22:00", "quiet_end": "07:00", "daily_limit": 2}).json()
    assert (p["quiet_start"], p["quiet_end"], p["daily_limit"]) == ("22:00:00", "07:00:00", 2)
    assert client.put("/alerts/preferences", headers=h, json={"push_subscription": {"endpoint": "x"}}).status_code == 422
    ok = client.put("/alerts/preferences", headers=h, json={"push_subscription": {
        "endpoint": "https://push.example/1", "keys": {"p256dh": "a", "auth": "b"}}}).json()
    assert ok["push_subscribed"]
    assert client.post("/alerts/evaluate", headers=h).status_code == 200


@needs_db
def test_meal_alerts_leave_room_for_shortfall_and_weekly_skips_calcium(conn_user):
    conn, user = conn_user
    day = datetime(2026, 11, 2, tzinfo=LONDON)
    for h in (8, 13, 19):                                  # three conflicting meals in one day
        s, items = _log(conn, user, CURRY_TEA, day.replace(hour=h))
        rules.after_meal(conn, user, s["meal_id"], items, s["result"], now=day.replace(hour=h, minute=2))
    assert rules._automatic_count_today(conn, user, day.replace(hour=20)) == 2      # third meal alert held back
    assert rules.shortfall(conn, user, now=day.replace(hour=20)) is not None         # the reserved slot


@needs_db
def test_weekly_pattern_ignores_low_priority_calcium(conn_user):
    conn, user = conn_user
    now = datetime.now(LONDON)
    milk_toast = [{"food_code": "11-1145", "grams": 36}, {"food_code": "12-313", "grams": 200}]   # calcium rule only (low phytate)
    for d in range(1, 6):
        _log(conn, user, milk_toast, (now - timedelta(days=d)).replace(hour=8, minute=0))
    assert rules.weekly_patterns(conn, user, now=now) == []


@needs_db
def test_malformed_subscription_does_not_break_dispatch(conn_user):
    conn, user = conn_user
    from psycopg.types.json import Jsonb
    _set(conn, user, push_subscription=Jsonb({"endpoint": "https://push.example/x", "keys": {"p256dh": "a", "auth": "b"}}))
    now = datetime(2026, 11, 8, 16, 0, tzinfo=LONDON)
    rules.create_alert(conn, user, type="timing", message="one", dedupe="m1", now=now, scheduled_for=now)
    rules.create_alert(conn, user, type="timing", message="two", dedupe="m2", now=now, scheduled_for=now)
    out = push.dispatch_due(conn, now=now, user_id=user.user_id)        # real sender, bad keys
    assert out["due"] == 2 and out["gone"] >= 1
    assert rules.get_prefs(conn, user)["push_subscription"] is None
