"""Per-admin local time using Mentor location settings."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from models import MentorSettings

_TZ_ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata",
}


def get_admin_timezone_settings(admin_id):
    if not admin_id:
        return None
    return MentorSettings.query.filter_by(admin_id=admin_id).first()


def get_admin_timezone_id(admin_id):
    row = get_admin_timezone_settings(admin_id)
    if row and row.timezone_id:
        tz = row.timezone_id.strip()
        return _TZ_ALIASES.get(tz, tz)
    return None


def get_admin_location_label(admin_id):
    row = get_admin_timezone_settings(admin_id)
    if not row or not row.timezone_id:
        return None
    city = (row.timezone_city or "").strip()
    country = (row.timezone_country or "").strip()
    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    if country:
        return country
    return row.timezone_id


def admin_now(admin_id):
    """Naive datetime in the admin's selected city timezone."""
    from services.app_time import app_now

    tz_id = get_admin_timezone_id(admin_id)
    if tz_id:
        try:
            return datetime.now(ZoneInfo(tz_id)).replace(tzinfo=None)
        except ZoneInfoNotFoundError:
            pass
    return app_now()
