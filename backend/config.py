import os
import re
from datetime import timezone, timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def normalize_database_url(raw_value):
    """Clean common Neon/Render copy-paste mistakes before SQLAlchemy parses the URL."""
    if not raw_value:
        return ""

    url = raw_value.strip()

    # Neon sometimes shows: psql 'postgresql://...'
    if url.lower().startswith("psql "):
        url = url[5:].strip()

    # Strip wrapping quotes from copy-paste
    if len(url) >= 2 and url[0] == url[-1] and url[0] in ("'", '"'):
        url = url[1:-1].strip()

    # SQLAlchemy expects postgresql:// not postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Use psycopg v3 driver (works on Python 3.12+ including 3.14 on Render)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    _raw_db_url = normalize_database_url(os.environ.get("DATABASE_URL", ""))
    if _raw_db_url and not re.match(r"^postgresql(\+psycopg)?://", _raw_db_url):
        raise ValueError(
            "DATABASE_URL must start with postgresql:// (not psql, no quotes). "
            "Example: postgresql://user:pass@host/db?sslmode=require"
        )

    SQLALCHEMY_DATABASE_URI = _raw_db_url or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Initial admin account, created automatically on first startup
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-password")

    # Frontend URL (GitHub Pages) — used for task links and login redirects
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")

    # Allowed CORS origins (comma-separated). Defaults to FRONTEND_URL.
    _cors_raw = os.environ.get("CORS_ORIGINS", "")
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()] or [FRONTEND_URL]

    # Session / cookie security (cross-origin frontend requires SameSite=None + Secure)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "None")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Application timezone offset (hours from UTC). Default: UTC.
    APP_TZ_OFFSET_HOURS = float(os.environ.get("APP_TZ_OFFSET_HOURS", "0"))

    @property
    def APP_TIMEZONE(self):
        return timezone(timedelta(hours=self.APP_TZ_OFFSET_HOURS))


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
