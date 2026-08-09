"""Application-local date/time using configured timezone offset."""

from datetime import datetime, timedelta

from flask import current_app


def app_timezone_offset_hours():
    try:
        return float(current_app.config.get("APP_TZ_OFFSET_HOURS", 0))
    except (TypeError, ValueError):
        return 0.0


def app_now():
    offset = app_timezone_offset_hours()
    return datetime.utcnow() + timedelta(hours=offset)


def app_today():
    return app_now().date()


def parse_date_iso(value):
    if not value:
        return None
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()
