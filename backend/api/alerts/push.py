"""Web Push delivery (P2). Uses VAPID keys from settings; subscriptions come from the browser's PushManager.

Delivery is best-effort: the in-app notification centre is the source of truth (ProjectDefinition.md risk table).
Expired subscriptions (404/410) are removed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import psycopg

from api.settings import get_settings

log = logging.getLogger("absorb.push")


def send_push(subscription: dict, payload: dict) -> str:
    """Returns 'sent', 'gone' (subscription expired) or 'failed'."""
    s = get_settings()
    if not (s.vapid_private_key and subscription):
        return "failed"
    from pywebpush import WebPushException, webpush

    try:
        webpush(subscription_info=subscription, data=json.dumps(payload), vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject}, ttl=3600)
        return "sent"
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        log.warning("push failed (%s): %s", code, str(e)[:200])
        return "gone" if code in (404, 410) else "failed"
    except (ValueError, TypeError, KeyError) as e:      # malformed subscription (bad keys): drop it
        log.warning("invalid push subscription: %s", str(e)[:200])
        return "gone"
    except Exception as e:                               # network etc.: keep the alert in-app, try nothing else
        log.warning("push error: %s", str(e)[:200])
        return "failed"


def dispatch_due(conn: psycopg.Connection, now: datetime | None = None, sender=send_push,
                 user_id: str | None = None) -> dict:
    """Mark due alerts as sent and push them to subscribed users. Called by the scheduler every minute."""
    now = now or datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("""SELECT a.alert_id, a.created_at, a.user_id, a.type, a.message, a.source_rule_id, a.meal_id,
                              p.push_subscription, p.enabled
                       FROM alerts a LEFT JOIN alert_preferences p ON p.user_id = a.user_id
                       WHERE a.sent_at IS NULL AND a.dismissed_at IS NULL AND a.scheduled_for <= %s
                         AND (%s::text IS NULL OR a.user_id = %s)
                       ORDER BY a.scheduled_for LIMIT 200""", (now, user_id, user_id))
        due = cur.fetchall()
    counts = {"due": len(due), "pushed": 0, "in_app_only": 0, "gone": 0}
    for a in due:
        result = "in_app_only"
        if a["push_subscription"] and a["enabled"]:
            try:
                result = sender(a["push_subscription"], {
                    "title": "Absorb", "body": a["message"], "type": a["type"],
                    "alert_id": str(a["alert_id"]), "meal_id": str(a["meal_id"]) if a["meal_id"] else None})
            except Exception as e:                       # one bad alert must never stop the others
                log.warning("dispatch error for %s: %s", a["alert_id"], str(e)[:200])
                result = "failed"
            if result == "gone":
                with conn.cursor() as cur:
                    cur.execute("UPDATE alert_preferences SET push_subscription = NULL WHERE user_id = %s", (a["user_id"],))
        counts["pushed" if result == "sent" else "gone" if result == "gone" else "in_app_only"] += 1
        with conn.cursor() as cur:
            cur.execute("UPDATE alerts SET sent_at = %s, data = data || %s::jsonb WHERE alert_id = %s AND created_at = %s",
                        (now, json.dumps({"delivery": result}), a["alert_id"], a["created_at"]))
    conn.commit()
    return counts
