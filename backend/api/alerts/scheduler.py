"""Background jobs (P2). Runs inside the API process when SCHEDULER_ENABLED=true (single instance).

- every minute:      deliver due alerts (timing reminders, alerts held through quiet hours)
- every 15 minutes:  shortfall check for users who logged a meal today (after the evening check hour)
- every hour:        weekly pattern check (deduplicated per ISO week)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from api import db
from api.alerts import push, rules
from api.auth import User

log = logging.getLogger("absorb.scheduler")
_scheduler = None


def _active_users(conn, days: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT user_id FROM meal_results WHERE eaten_at >= %s",
                    (datetime.now(timezone.utc) - timedelta(days=days),))
        return [r["user_id"] for r in cur.fetchall()]


def job_dispatch() -> None:
    with db.pool().connection() as conn:
        counts = push.dispatch_due(conn)
        if counts["due"]:
            log.info("dispatched %s", counts)


def job_shortfall() -> None:
    with db.pool().connection() as conn:
        for uid in _active_users(conn, 1):
            try:
                rules.shortfall(conn, User(uid))
            except Exception:
                log.exception("shortfall check failed for %s", uid)


def job_weekly() -> None:
    with db.pool().connection() as conn:
        for uid in _active_users(conn, rules.PATTERN_DAYS):
            try:
                rules.weekly_patterns(conn, User(uid))
            except Exception:
                log.exception("weekly check failed for %s", uid)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(timezone="Europe/London")
    _scheduler.add_job(job_dispatch, "interval", minutes=1, id="dispatch", max_instances=1, coalesce=True)
    _scheduler.add_job(job_shortfall, "interval", minutes=15, id="shortfall", max_instances=1, coalesce=True)
    _scheduler.add_job(job_weekly, "interval", hours=1, id="weekly", max_instances=1, coalesce=True)
    _scheduler.start()
    log.info("scheduler started")


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
