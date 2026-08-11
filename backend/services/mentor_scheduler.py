"""Mentor proactive check-in scheduler."""

from apscheduler.triggers.interval import IntervalTrigger

_mentor_scheduler = None


def start_mentor_scheduler(app):
    global _mentor_scheduler
    if _mentor_scheduler is not None:
        return

    def _tick():
        with app.app_context():
            from services.mentor_service import process_due_checkins
            from models import Admin

            process_due_checkins()
            for admin in Admin.query.all():
                from services.mentor_service import schedule_hourly_timetable_checkins

                try:
                    schedule_hourly_timetable_checkins(admin.id)
                except Exception:
                    app.logger.exception("Mentor hourly check-in failed for admin %s", admin.id)

    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_tick, IntervalTrigger(minutes=5), id="mentor_tick", replace_existing=True)
    scheduler.start()
    _mentor_scheduler = scheduler
    app.logger.info("Mentor proactive scheduler started (5 min interval)")
