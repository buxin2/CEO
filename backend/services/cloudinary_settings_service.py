"""Cloudinary credentials stored in the database (admin configures in AI Assistant)."""

from models import db, CloudinarySettings
from services.groq_key_service import decrypt_api_key, encrypt_api_key


def _mask_secret(secret):
    if not secret:
        return "••••••••••••••••••••"
    s = secret.strip()
    if len(s) <= 4:
        return "••••••••••••••••••••"
    return "••••••••••••••••••" + s[-4:]


def get_settings_row():
    row = CloudinarySettings.query.first()
    if not row:
        row = CloudinarySettings()
        db.session.add(row)
        db.session.commit()
    return row


def get_cloudinary_credentials():
    """Return dict with cloud_name, api_key, api_secret or None if not configured."""
    row = get_settings_row()
    cloud_name = (row.cloud_name or "").strip()
    api_key = decrypt_api_key(row.encrypted_api_key) if row.encrypted_api_key else ""
    api_secret = decrypt_api_key(row.encrypted_api_secret) if row.encrypted_api_secret else ""
    if cloud_name and api_key and api_secret:
        return {
            "cloud_name": cloud_name,
            "api_key": api_key,
            "api_secret": api_secret,
        }
    return None


def is_cloudinary_configured_in_db():
    return get_cloudinary_credentials() is not None


def settings_to_dict():
    row = get_settings_row()
    creds = get_cloudinary_credentials()
    api_key_plain = creds["api_key"] if creds else ""
    api_secret_plain = creds["api_secret"] if creds else ""
    return {
        "configured": creds is not None,
        "cloud_name": row.cloud_name or "",
        "masked_api_key": _mask_secret(api_key_plain) if api_key_plain else "",
        "masked_api_secret": _mask_secret(api_secret_plain),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def update_settings(cloud_name=None, api_key=None, api_secret=None):
    row = get_settings_row()
    if cloud_name is not None:
        name = (cloud_name or "").strip()
        if not name:
            raise ValueError("Cloud name is required.")
        row.cloud_name = name[:80]

    if api_key is not None:
        key = (api_key or "").strip()
        if key:
            row.encrypted_api_key = encrypt_api_key(key)
        elif not row.encrypted_api_key:
            raise ValueError("API key is required.")

    if api_secret is not None:
        secret = (api_secret or "").strip()
        if secret:
            row.encrypted_api_secret = encrypt_api_key(secret)
        elif not row.encrypted_api_secret:
            raise ValueError("API secret is required.")

    if not row.cloud_name or not row.encrypted_api_key or not row.encrypted_api_secret:
        raise ValueError("Cloud name, API key, and API secret are all required.")

    db.session.commit()
    return settings_to_dict()
