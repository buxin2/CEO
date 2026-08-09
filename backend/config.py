import os
from datetime import timezone, timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # Render/Neon provide DATABASE_URL like postgres://... -- SQLAlchemy needs postgresql://
    _raw_db_url = os.environ.get("DATABASE_URL", "")
    if _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)

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
