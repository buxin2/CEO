"""Groq API key storage, encryption, and active-key resolution."""

import hashlib
import re
from base64 import urlsafe_b64encode
from datetime import datetime

from flask import current_app
from cryptography.fernet import Fernet, InvalidToken

from models import db, GroqApiKey

KEY_PATTERN = re.compile(r"^gsk_[A-Za-z0-9]+$")


def _fernet():
    secret = current_app.config.get("SECRET_KEY", "dev-secret")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(urlsafe_b64encode(digest))


def encrypt_api_key(plain_key):
    return _fernet().encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key):
    if not encrypted_key:
        return ""
    try:
        return _fernet().decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def mask_api_key(plain_key):
    if not plain_key:
        return "••••••••••••••••••••"
    key = plain_key.strip()
    if len(key) <= 8:
        return "••••••••••••••••••••"
    if key.startswith("gsk_"):
        return f"gsk_••••••••••••••••••{key[-4:]}"
    return "••••••••••••••••••" + key[-4:]


def validate_api_key_format(key):
    key = (key or "").strip()
    if not key:
        return False, "API key is required."
    if not KEY_PATTERN.match(key):
        return False, "Groq API keys should start with gsk_ and contain only letters and numbers."
    return True, key


def default_model():
    return current_app.config.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def is_groq_configured():
    return get_active_groq_config() is not None


def get_active_groq_config():
    """
    Return active API config. Database active key takes priority over environment variable.
    """
    record = GroqApiKey.query.filter_by(is_active=True).first()
    if record:
        plain = decrypt_api_key(record.encrypted_key)
        if plain:
            model = (record.model or "").strip() or default_model()
            return {
                "api_key": plain,
                "model": model,
                "key_id": record.id,
                "source": "database",
                "key_name": record.name,
            }

    env_key = (current_app.config.get("GROQ_API_KEY") or "").strip()
    if env_key:
        return {
            "api_key": env_key,
            "model": default_model(),
            "key_id": None,
            "source": "environment",
            "key_name": "Environment variable",
        }
    return None


def mark_key_used(key_id):
    if not key_id:
        return
    record = GroqApiKey.query.get(key_id)
    if record:
        record.last_used_at = datetime.utcnow()
        db.session.commit()


def activate_key(key_id):
    record = GroqApiKey.query.get(key_id)
    if not record:
        raise ValueError("API key not found.")
    GroqApiKey.query.update({GroqApiKey.is_active: False})
    record.is_active = True
    db.session.commit()
    return record


def list_keys():
    return GroqApiKey.query.order_by(GroqApiKey.created_at.asc()).all()


def create_key(name, api_key, description="", model=""):
    ok, result = validate_api_key_format(api_key)
    if not ok:
        raise ValueError(result)

    name = (name or "").strip()
    if not name:
        raise ValueError("API name is required.")

    record = GroqApiKey(
        name=name,
        description=(description or "").strip(),
        encrypted_key=encrypt_api_key(result),
        model=(model or "").strip(),
        is_active=False,
    )
    db.session.add(record)
    db.session.commit()

    if GroqApiKey.query.filter_by(is_active=True).count() == 0:
        activate_key(record.id)

    return record


def update_key(key_id, name=None, api_key=None, description=None, model=None):
    record = GroqApiKey.query.get(key_id)
    if not record:
        raise ValueError("API key not found.")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("API name cannot be empty.")
        record.name = name

    if description is not None:
        record.description = description.strip()

    if model is not None:
        record.model = model.strip()

    if api_key is not None and api_key.strip():
        ok, result = validate_api_key_format(api_key)
        if not ok:
            raise ValueError(result)
        record.encrypted_key = encrypt_api_key(result)
        record.last_test_status = ""
        record.last_test_message = ""

    db.session.commit()
    return record


def delete_key(key_id):
    record = GroqApiKey.query.get(key_id)
    if not record:
        raise ValueError("API key not found.")

    was_active = record.is_active
    db.session.delete(record)
    db.session.commit()

    if was_active:
        replacement = GroqApiKey.query.order_by(GroqApiKey.created_at.asc()).first()
        if replacement:
            activate_key(replacement.id)
            return {"activated_replacement_id": replacement.id}

    return {"activated_replacement_id": None}


def test_groq_key(api_key, model=None):
    model = (model or "").strip() or default_model()
    ok, key = validate_api_key_format(api_key)
    if not ok:
        return {"status": "failed", "message": key}

    try:
        from groq import Groq

        client = Groq(api_key=key)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=8,
            temperature=0,
        )
        return {"status": "ok", "message": "API Working"}
    except Exception as exc:
        text = str(exc).lower()
        if "authentication" in text or "invalid api key" in text or "401" in text:
            return {"status": "auth_error", "message": "Authentication failed. Check the API key."}
        if "rate limit" in text or "429" in text:
            return {"status": "rate_limit", "message": "Rate limit reached. Try again later."}
        if "quota" in text:
            return {"status": "quota", "message": "Quota or usage limit issue reported by Groq."}
        return {"status": "failed", "message": "API test failed. Verify the key and model."}


def test_saved_key(key_id):
    record = GroqApiKey.query.get(key_id)
    if not record:
        raise ValueError("API key not found.")

    plain = decrypt_api_key(record.encrypted_key)
    if not plain:
        result = {"status": "failed", "message": "Stored key could not be decrypted."}
    else:
        result = test_groq_key(plain, record.model)

    record.last_tested_at = datetime.utcnow()
    record.last_test_status = result["status"]
    record.last_test_message = result["message"]
    db.session.commit()
    return result
