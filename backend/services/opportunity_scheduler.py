"""Schedule daily opportunity report at midnight (app timezone)."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = None


def start_opportunity_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return

    offset = float(app.config.get("APP_TZ_OFFSET_HOURS", 0))
    # Cron uses server local time; offset hours shift trigger to approximate app TZ from UTC server
    utc_hour = (0 - int(offset)) % 24

    def _job():
        with app.app_context():
            from services.opportunity_service import generate_daily_report

            try:
                generate_daily_report()
            except Exception:
                app.logger.exception("Scheduled opportunity report failed")

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _job,
        CronTrigger(hour=utc_hour, minute=0),
        id="daily_opportunity_report",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    app.logger.info(
        "Opportunity scheduler started (daily at 00:00 app TZ, cron hour=%s UTC-offset)",
        utc_hour,
    )
