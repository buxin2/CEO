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

    if url.lower().startswith("psql "):
        url = url[5:].strip()

    if len(url) >= 2 and url[0] == url[-1] and url[0] in ("'", '"'):
        url = url[1:-1].strip()

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

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


def _load_manual_payment_instructions():
    raw = os.environ.get("MANUAL_PAYMENT_INSTRUCTIONS_JSON", "")
    if raw:
        try:
            import json

            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {
        "bank_transfer": {
            "title": "Bank Transfer (Ecobank Gambia)",
            "fields": [
                {"label": "Account holder", "value": "Abdoukadir Jabbi"},
                {"label": "Bank", "value": "Ecobank Gambia Ltd"},
                {"label": "Account number", "value": "6261010783"},
                {"label": "IBAN", "value": "008203626101078387"},
                {"label": "SWIFT / BIC", "value": "ECOCGMGM"},
                {"label": "Country", "value": "The Gambia"},
                {"label": "Currency", "value": "USD / GMD"},
                {"label": "Reference", "value": "Your full name + Buxin Academy"},
            ],
        },
        "money_transfer": {
            "title": "Money Transfer (Western Union / MoneyGram / Ria)",
            "fields": [
                {"label": "Receiver name", "value": "ABDOUKADIR JABBI"},
                {"label": "Country", "value": "India"},
                {"label": "City", "value": "Greater Noida, Uttar Pradesh"},
                {"label": "Phone", "value": "+91 931 903 8312"},
            ],
        },
    }


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

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-password")

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
    CORS_ORIGINS = build_cors_origins()

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "None")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    APP_TZ_OFFSET_HOURS = float(os.environ.get("APP_TZ_OFFSET_HOURS", "0"))

    GROQ_API_KEY = (
        os.environ.get("GROQ_API_KEY") or os.environ.get("GROK_API_KEY") or ""
    ).strip()
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    SERPER_API_KEY = (os.environ.get("SERPER_API_KEY") or "").strip()
    NEWS_CRON_SECRET = (os.environ.get("NEWS_CRON_SECRET") or "").strip()
    ADMIN_DISPLAY_NAME = (os.environ.get("ADMIN_DISPLAY_NAME") or "").strip()

    CLOUDINARY_URL = (os.environ.get("CLOUDINARY_URL") or "").strip()
    CLOUDINARY_CLOUD_NAME = (os.environ.get("CLOUDINARY_CLOUD_NAME") or "").strip()
    CLOUDINARY_API_KEY = (os.environ.get("CLOUDINARY_API_KEY") or "").strip()
    CLOUDINARY_API_SECRET = (os.environ.get("CLOUDINARY_API_SECRET") or "").strip()

    BACKEND_URL = (os.environ.get("BACKEND_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    PAYPAL_CLIENT_ID = (os.environ.get("PAYPAL_CLIENT_ID") or "").strip()
    PAYPAL_CLIENT_SECRET = (os.environ.get("PAYPAL_CLIENT_SECRET") or "").strip()
    PAYPAL_MODE = (os.environ.get("PAYPAL_MODE") or "live").strip().lower()
    MODEMPAY_PUBLIC_KEY = (os.environ.get("MODEMPAY_PUBLIC_KEY") or "").strip()
    MODEMPAY_SECRET_KEY = (os.environ.get("MODEMPAY_SECRET_KEY") or "").strip()
    MODEMPAY_WEBHOOK_SECRET = (os.environ.get("MODEMPAY_WEBHOOK_SECRET") or "").strip()
    MANUAL_PAYMENT_INSTRUCTIONS = _load_manual_payment_instructions()

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
