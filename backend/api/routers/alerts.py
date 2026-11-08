"""Notification centre, alert preferences, accepted reminders and Web Push subscription."""
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from api.alerts import rules
from api.alerts.rules import serialise
from api.auth import User, current_user
from api.db import get_conn
from api.settings import get_settings

router = APIRouter(tags=["alerts"])
ALL_TYPES = ["conflict", "data_gap", "timing", "shortfall", "weekly_pattern"]


@router.get("/alerts")
def list_alerts(unread_only: bool = False, limit: int = Query(50, ge=1, le=200),
                user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    """Alerts that are due (held alerts appear once their time comes). Newest first."""
    sql = ("SELECT * FROM alerts WHERE user_id = %s AND dismissed_at IS NULL AND scheduled_for <= %s"
           + (" AND read_at IS NULL" if unread_only else "") + " ORDER BY scheduled_for DESC LIMIT %s")
    with conn.cursor() as cur:
        cur.execute(sql, (user.user_id, datetime.now(timezone.utc), limit))
        rows = [serialise(r) for r in cur.fetchall()]
        cur.execute("SELECT count(*) AS n FROM alerts WHERE user_id = %s AND dismissed_at IS NULL AND read_at IS NULL "
                    "AND scheduled_for <= %s", (user.user_id, datetime.now(timezone.utc)))
        unread = cur.fetchone()["n"]
    return {"alerts": rows, "unread": unread}


class AlertPatch(BaseModel):
    read: bool | None = None
    dismissed: bool | None = None


@router.patch("/alerts/{alert_id}")
def patch_alert(alert_id: uuid.UUID, body: AlertPatch, user: User = Depends(current_user),
                conn: psycopg.Connection = Depends(get_conn)):
    sets = []
    if body.read is not None:
        sets.append("read_at = " + ("now()" if body.read else "NULL"))
    if body.dismissed is not None:
        sets.append("dismissed_at = " + ("now()" if body.dismissed else "NULL"))
    if not sets:
        raise HTTPException(422, "Nothing to change")
    with conn.cursor() as cur:
        cur.execute(f"UPDATE alerts SET {', '.join(sets)} WHERE alert_id = %s AND user_id = %s RETURNING *",
                    (alert_id, user.user_id))
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return serialise(row)


class ReminderIn(BaseModel):
    """A reminder the user accepted (from a fix or a chat proposal)."""
    type: Literal["timing"] = "timing"
    remind_at: datetime
    message: str = Field(min_length=1, max_length=200)
    meal_id: uuid.UUID | None = None


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_reminder(body: ReminderIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    if body.remind_at.tzinfo is None:
        raise HTTPException(422, "remind_at needs a time zone, e.g. 2026-11-08T15:00:00+00:00")
    a = rules.create_alert(conn, user, type="timing", message=body.message, scheduled_for=body.remind_at,
                           dedupe=f"timing:{uuid.uuid4()}", meal_id=str(body.meal_id) if body.meal_id else None)
    if a is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Timing reminders are turned off in your alert preferences")
    return a


@router.post("/alerts/evaluate")
def evaluate(user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    """Run the daily shortfall and weekly pattern checks now for the signed-in user (the scheduler does this too)."""
    created = []
    s = rules.shortfall(conn, user)
    if s:
        created.append(s)
    created += rules.weekly_patterns(conn, user)
    return {"created": created}


# ----------------------------------------------------------------------------- preferences and push

class PrefsIn(BaseModel):
    enabled: bool | None = None
    enabled_types: list[Literal["conflict", "data_gap", "timing", "shortfall", "weekly_pattern"]] | None = None
    quiet_start: time | None = None
    quiet_end: time | None = None
    daily_limit: int | None = Field(None, ge=0, le=20)
    push_subscription: dict | None = Field(None, description="PushSubscription.toJSON() from the browser; {} to remove")


def _prefs_out(row: dict) -> dict:
    out = {k: row[k] for k in ("enabled", "enabled_types", "daily_limit")}
    out["quiet_start"] = row["quiet_start"].isoformat() if row["quiet_start"] else None
    out["quiet_end"] = row["quiet_end"].isoformat() if row["quiet_end"] else None
    out["push_subscribed"] = bool(row["push_subscription"])
    out["all_types"] = ALL_TYPES
    return out


@router.get("/alerts/preferences")
def get_prefs(user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    return _prefs_out(rules.get_prefs(conn, user))


@router.put("/alerts/preferences")
def put_prefs(body: PrefsIn, user: User = Depends(current_user), conn: psycopg.Connection = Depends(get_conn)):
    rules.get_prefs(conn, user)
    fields = body.model_dump(exclude_unset=True)
    if "push_subscription" in fields:
        sub = fields["push_subscription"]
        if sub and not (sub.get("endpoint") and sub.get("keys", {}).get("p256dh") and sub.get("keys", {}).get("auth")):
            raise HTTPException(422, "push_subscription must have endpoint and keys.p256dh / keys.auth")
        fields["push_subscription"] = Jsonb(sub) if sub else None
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields) + ", updated_at = now()"
        with conn.cursor() as cur:
            cur.execute(f"UPDATE alert_preferences SET {sets} WHERE user_id = %s", (*fields.values(), user.user_id))
        conn.commit()
    return _prefs_out(rules.get_prefs(conn, user))


@router.get("/alerts/push/public-key")
def push_public_key():
    key = get_settings().vapid_public_key
    if not key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Web Push is not configured")
    return {"public_key": key}
