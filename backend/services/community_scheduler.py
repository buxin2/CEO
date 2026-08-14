"""Run scheduled community AI/admin messages."""

import logging
from datetime import datetime, timedelta

from models import db, CommunityScheduledMessage
from services.app_time import app_now
from services.community_service import create_post

logger = logging.getLogger(__name__)

_scheduler = None


def compute_next_run(row, now=None):
    now = now or app_now()
    kind = (row.schedule_kind or "once").lower()
    time_hm = (row.schedule_time or "09:00")[:5]
    try:
        hour, minute = map(int, time_hm.split(":"))
    except ValueError:
        hour, minute = 9, 0

    if kind == "once":
        if row.scheduled_at and row.scheduled_at > now:
            return row.scheduled_at
        return None

    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if kind == "daily":
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if kind == "weekly":
        target_day = row.schedule_weekday if row.schedule_weekday is not None else 0
        days_ahead = (target_day - now.weekday()) % 7
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    return None


def process_scheduled_messages():
    now = app_now()
    due = CommunityScheduledMessage.query.filter_by(is_active=True).filter(
        CommunityScheduledMessage.next_run_at.isnot(None),
        CommunityScheduledMessage.next_run_at <= now,
    ).all()
    for row in due:
        try:
            create_post(
                row.community_id,
                row.message,
                admin_id=None,
                is_announcement=row.is_announcement,
            )
            row.last_sent_at = now
            if (row.schedule_kind or "").lower() == "once":
                row.is_active = False
                row.next_run_at = None
            else:
                row.next_run_at = compute_next_run(row, now)
        except Exception:
            logger.exception("Failed scheduled community message %s", row.id)
    db.session.commit()


def start_community_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return

    def _tick():
        with app.app_context():
            try:
                process_scheduled_messages()
            except Exception:
                app.logger.exception("Scheduled community messages job failed")

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            _tick,
            IntervalTrigger(minutes=1),
            id="community_scheduled_messages",
            replace_existing=True,
        )
        scheduler.start()
        _scheduler = scheduler
        app.config["COMMUNITY_SCHEDULER"] = scheduler
        app.logger.info("Community scheduler started (1 min interval)")
    except Exception:
        logger.exception("Community scheduler failed to start")
