import os
import re
from datetime import timezone, timedelta
from urllib.parse import urlparse

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


def cors_origin_variants(url):
    """Expand CORS origins for GitHub Pages project sites (Origin is host only, no /CEO path)."""
    url = url.rstrip("/")
    variants = [url]
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith("github.io") and parsed.path and parsed.path != "/":
        variants.append(f"{parsed.scheme}://{parsed.hostname}")
    return variants


def build_cors_origins():
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
    cors_raw = os.environ.get("CORS_ORIGINS", "")
    seeds = [o.strip().rstrip("/") for o in cors_raw.split(",") if o.strip()] or [frontend_url]

    origins = []
    for seed in seeds:
        for origin in cors_origin_variants(seed):
            if origin not in origins:
                origins.append(origin)
    return origins


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
    # GitHub Pages project sites also need https://user.github.io (no repo path).
    CORS_ORIGINS = build_cors_origins()

    # Session / cookie security (cross-origin frontend requires SameSite=None + Secure)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "None")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Application timezone offset (hours from UTC). Default: UTC.
    APP_TZ_OFFSET_HOURS = float(os.environ.get("APP_TZ_OFFSET_HOURS", "0"))

    # Groq API for AI Management Assistant (gsk_... key from console.groq.com)
    # GROK_API_KEY is accepted as an alias for convenience.
    GROQ_API_KEY = (
        os.environ.get("GROQ_API_KEY") or os.environ.get("GROK_API_KEY") or ""
    ).strip()
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Optional: Serper.dev for better web search in News (https://serper.dev)
    SERPER_API_KEY = (os.environ.get("SERPER_API_KEY") or "").strip()

    # Optional: secret for external cron hitting POST /api/news/cron at midnight
    NEWS_CRON_SECRET = (os.environ.get("NEWS_CRON_SECRET") or "").strip()

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
