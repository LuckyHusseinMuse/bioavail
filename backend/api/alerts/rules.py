"""Deterministic alert rules (ProjectDefinition.md section 7.2.2). The LLM never decides when an alert fires.

Alert types
- conflict        a logged meal fires a conflict rule (message from the rule, plus the engine's top fix)
- data_gap        a logged meal includes foods without inhibitor data
- shortfall       after the evening check hour, today's share of potential < 50% or absorbed < half the target
- weekly_pattern  the same conflict at the same meal slot 3+ times in the last 7 days (once per ISO week)
- timing          a reminder the user accepted (from a fix or a chat proposal)

Controls: master switch, per-type switches, quiet hours (alerts are held until they end, not dropped),
daily limit for automatic alerts, and a dedupe key so the same alert is never created twice.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

from absorb_engine import MealItem
from absorb_engine.daily import LOW_SHARE_OF_POTENTIAL_PCT
from absorb_engine.fixes import suggest_fixes
from api.auth import User
from api.services import daily_view, ensure_user, ref

AUTOMATIC = {"conflict", "data_gap", "shortfall", "weekly_pattern"}
MEAL_ALERTS = {"conflict", "data_gap"}
PATTERN_MAX_PRIORITY = 2      # rules with recommendation_priority above this (e.g. calcium) are not nagged about weekly
EVENING_CHECK_HOUR = 18
PATTERN_MIN_TIMES = 3
PATTERN_DAYS = 7


def _tz(profile: dict) -> ZoneInfo:
    return ZoneInfo(profile.get("timezone") or "Europe/London")


def get_prefs(conn: psycopg.Connection, user: User) -> dict:
    ensure_user(conn, user)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM alert_preferences WHERE user_id = %s", (user.user_id,))
        return cur.fetchone()


def in_quiet_hours(local: datetime, start: time | None, end: time | None) -> bool:
    if not start or not end or start == end:
        return False
    t = local.timetz().replace(tzinfo=None)
    return start <= t < end if start < end else (t >= start or t < end)   # overnight window, e.g. 22:00-07:00


def quiet_end_after(local: datetime, end: time) -> datetime:
    candidate = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return candidate if candidate > local else candidate + timedelta(days=1)


def _automatic_count_today(conn: psycopg.Connection, user: User, local_now: datetime) -> int:
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM alerts WHERE user_id = %s AND created_at >= %s AND created_at < %s "
                    "AND type = ANY(%s)", (user.user_id, start, end, list(AUTOMATIC)))
        return cur.fetchone()["n"]


def _exists(conn: psycopg.Connection, user: User, dedupe: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM alerts WHERE user_id = %s AND data->>'dedupe' = %s LIMIT 1", (user.user_id, dedupe))
        return cur.fetchone() is not None


def create_alert(conn: psycopg.Connection, user: User, *, type: str, message: str, dedupe: str,
                 now: datetime | None = None, scheduled_for: datetime | None = None, source_rule_id: str | None = None,
                 meal_id: str | None = None, data: dict | None = None, profile: dict | None = None) -> dict | None:
    """Create one alert if preferences allow. Returns the alert, or None if suppressed (with the reason logged in data)."""
    now = now or datetime.now(timezone.utc)
    profile = profile or ensure_user(conn, user)
    prefs = get_prefs(conn, user)
    tz = _tz(profile)
    if not prefs["enabled"] or type not in prefs["enabled_types"]:
        return None
    if _exists(conn, user, dedupe):
        return None
    if type in AUTOMATIC:
        used = _automatic_count_today(conn, user, now.astimezone(tz))
        limit = prefs["daily_limit"]
        # Meal alerts leave one slot free so the evening shortfall or weekly summary can still get through.
        if type in MEAL_ALERTS and limit > 1:
            limit -= 1
        if used >= limit:
            return None
    due = scheduled_for or now
    local_due = due.astimezone(tz)
    if in_quiet_hours(local_due, prefs["quiet_start"], prefs["quiet_end"]):
        due = quiet_end_after(local_due, prefs["quiet_end"]).astimezone(timezone.utc)
    alert_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO alerts (alert_id, user_id, created_at, type, scheduled_for, message, source_rule_id, "
                    "meal_id, data) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (alert_id, user.user_id, now, type, due, message, source_rule_id,
                     uuid.UUID(meal_id) if meal_id else None, Jsonb({**(data or {}), "dedupe": dedupe})))
        row = cur.fetchone()
    conn.commit()
    return serialise(row)


def serialise(row: dict) -> dict:
    out = dict(row)
    for k in ("alert_id", "meal_id"):
        out[k] = str(out[k]) if out.get(k) else None
    for k in ("created_at", "scheduled_for", "sent_at", "read_at", "dismissed_at"):
        out[k] = out[k].isoformat() if out.get(k) else None
    return out


# ----------------------------------------------------------------------------- rules

def after_meal(conn: psycopg.Connection, user: User, meal_id: str, items: list[MealItem], result: dict,
               now: datetime | None = None) -> list[dict]:
    """Conflict and data-gap alerts for a just-logged meal."""
    created = []
    if result["conflicts"]:
        top = result["conflicts"][0]
        fixes = suggest_fixes(items, ref(), top_n=1)["fixes"]
        tip = f" Try: {fixes[0]['change']['description'].lower()}." if fixes else ""
        a = create_alert(conn, user, type="conflict", message=top["message"] + tip, dedupe=f"conflict:{meal_id}",
                         now=now, source_rule_id=top["rule_id"], meal_id=meal_id,
                         data={"reduction_pct": top["reduction_pct"], "evidence_id": top["evidence_id"],
                               "fix": fixes[0]["change"] if fixes else None,
                               "fix_gain_mg": fixes[0]["gain_mg"] if fixes else None})
        if a:
            created.append(a)
    gaps = sorted({g["name"] for g in result["data_gaps"]})
    if gaps:
        what = gaps[0] if len(gaps) == 1 else f"{len(gaps)} items"
        a = create_alert(conn, user, type="data_gap", dedupe=f"data_gap:{meal_id}", now=now, meal_id=meal_id,
                         message=f"We couldn't check {what} for inhibitors, so this estimate may be high.",
                         data={"foods": gaps})
        if a:
            created.append(a)
    return created


def shortfall(conn: psycopg.Connection, user: User, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(timezone.utc)
    profile = ensure_user(conn, user)
    local = now.astimezone(_tz(profile))
    if local.hour < EVENING_CHECK_HOUR:
        return None
    day = daily_view(conn, user, local.date(), profile)
    t, p = day["totals"], day["progress"]
    if t["meals"] == 0:
        return None
    low_share = t["share_of_potential_pct"] is not None and t["share_of_potential_pct"] < LOW_SHARE_OF_POTENTIAL_PCT
    low_target = p["absorbed_share_of_target"] < 0.5
    if not (low_share or low_target):
        return None
    if low_share:
        msg = (f"Today's meals and drinks blocked {100 - t['share_of_potential_pct']}% of the iron available "
               f"({t['inhibitors_cost_mg']} mg). A vitamin C rich side with dinner, and no tea with it, would help.")
    else:
        msg = (f"You've absorbed {t['absorbed_mg']} mg of iron today, under half your "
               f"{day['references']['absorbed_target_mg_day']} mg target. An iron-rich dinner with vitamin C would help.")
    return create_alert(conn, user, type="shortfall", message=msg, dedupe=f"shortfall:{local.date().isoformat()}",
                        now=now, data={"totals": t, "progress": p})


def weekly_patterns(conn: psycopg.Connection, user: User, now: datetime | None = None) -> list[dict]:
    from api.agents.tools import ToolContext, call_tool

    now = now or datetime.now(timezone.utc)
    profile = ensure_user(conn, user)
    week = now.astimezone(_tz(profile)).isocalendar()
    pats = call_tool(ToolContext(user=user, conn=conn), "get_patterns", {"days": PATTERN_DAYS})
    candidates = [p for p in pats.get("recurring_conflicts", [])
                  if p["times"] >= PATTERN_MIN_TIMES and p["rule_id"] in ref().rules
                  and ref().rules[p["rule_id"]].priority <= PATTERN_MAX_PRIORITY]
    # One summary per week: the single habit costing the most absorbed iron.
    candidates = sorted(candidates, key=lambda p: -p["lost_mg"])[:1]
    created = []
    for p in candidates:
        rule = ref().rules.get(p["rule_id"])
        what = {"Black_Tea": "Tea", "Coffee": "Coffee", "Polyphenol_Rich_Beverage": "A tea, coffee or cocoa",
                "High_Phytate_Meal": "Phytate without vitamin C", "High_Calcium_Meal": "A lot of calcium"}.get(
                    rule.trigger_entity if rule else "", "The same conflict")
        msg = (f"{what} with {p['slot']} {p['times']} times this week cost you about {p['lost_mg']} mg of absorbed iron. "
               f"Changing that one habit is your biggest win.")
        a = create_alert(conn, user, type="weekly_pattern", message=msg, now=now, source_rule_id=p["rule_id"],
                         dedupe=f"weekly:{week.year}-W{week.week:02d}", data=p)
        if a:
            created.append(a)
    return created
