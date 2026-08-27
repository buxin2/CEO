"""Admin-managed PayPal and Modem Pay credentials. Database wins over env vars."""

from flask import current_app

from models import db, PaymentSettings
from services.groq_key_service import decrypt_api_key, encrypt_api_key, mask_api_key


def get_settings_row():
    row = PaymentSettings.query.first()
    if not row:
        row = PaymentSettings(mode="live", brand_name="Store")
        db.session.add(row)
        db.session.commit()
    return row


def _dec(value):
    return decrypt_api_key(value) if value else ""


def _env(name):
    return (current_app.config.get(name) or "").strip()


def get_active_credentials():
    row = get_settings_row()
    mode = (row.mode or "live").strip().lower()
    if mode not in ("live", "test"):
        mode = "live"

    live_id = _dec(row.enc_paypal_client_id) or _env("PAYPAL_CLIENT_ID")
    live_secret = _dec(row.enc_paypal_secret) or _env("PAYPAL_CLIENT_SECRET")
    sand_id = _dec(row.enc_paypal_sandbox_client_id)
    sand_secret = _dec(row.enc_paypal_sandbox_secret)
    modem_secret = _dec(row.enc_modem_secret) or _env("MODEMPAY_SECRET_KEY")
    modem_test = _dec(row.enc_modem_test_secret)
    modem_public = _dec(row.enc_modem_public_key) or _env("MODEMPAY_PUBLIC_KEY")
    modem_wh = _dec(row.enc_modem_webhook_secret) or _env("MODEMPAY_WEBHOOK_SECRET")
    brand = (row.brand_name or "").strip() or _env("PAYPAL_BRAND_NAME") or "Store"

    if mode == "test":
        paypal_id = sand_id or live_id
        paypal_secret = sand_secret or live_secret
        paypal_api = "sandbox"
        modem_use = modem_test or modem_secret
    else:
        paypal_id = live_id
        paypal_secret = live_secret
        paypal_api = "live"
        modem_use = modem_secret

    return {
        "mode": mode,
        "brand_name": brand,
        "paypal_client_id": paypal_id,
        "paypal_client_secret": paypal_secret,
        "paypal_mode": paypal_api,
        "modem_public_key": modem_public,
        "modem_secret_key": modem_use,
        "modem_webhook_secret": modem_wh,
    }


def settings_public_dict():
    row = get_settings_row()
    creds = get_active_credentials()
    return {
        "mode": creds["mode"],
        "brand_name": creds["brand_name"],
        "paypal_configured": bool(creds["paypal_client_id"] and creds["paypal_client_secret"]),
        "modem_configured": bool(creds["modem_secret_key"]),
        "paypal_client_id_masked": mask_api_key(creds["paypal_client_id"]) if creds["paypal_client_id"] else "",
        "paypal_secret_masked": mask_api_key(creds["paypal_client_secret"]) if creds["paypal_client_secret"] else "",
        "paypal_sandbox_client_id_masked": mask_api_key(_dec(row.enc_paypal_sandbox_client_id)) if row.enc_paypal_sandbox_client_id else "",
        "paypal_sandbox_secret_masked": mask_api_key(_dec(row.enc_paypal_sandbox_secret)) if row.enc_paypal_sandbox_secret else "",
        "modem_public_masked": mask_api_key(creds["modem_public_key"]) if creds["modem_public_key"] else "",
        "modem_secret_masked": mask_api_key(_dec(row.enc_modem_secret) or _env("MODEMPAY_SECRET_KEY")) if (_dec(row.enc_modem_secret) or _env("MODEMPAY_SECRET_KEY")) else "",
        "modem_webhook_masked": mask_api_key(creds["modem_webhook_secret"]) if creds["modem_webhook_secret"] else "",
        "modem_test_secret_masked": mask_api_key(_dec(row.enc_modem_test_secret)) if row.enc_modem_test_secret else "",
        "env_fallback": {
            "paypal": bool(_env("PAYPAL_CLIENT_ID")),
            "modem": bool(_env("MODEMPAY_SECRET_KEY")),
        },
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "test_note": "Card/PayPal and Wave cannot charge $0.00. Tests use $0.01 (PayPal) or 1 GMD (Wave/AfriMoney/QMoney).",
    }


def _set_enc(row, field, value):
    text = (value or "").strip()
    if not text:
        return
    if set(text) <= set("•."):
        return
    setattr(row, field, encrypt_api_key(text))


def update_settings(data):
    row = get_settings_row()
    if data.get("mode") is not None:
        mode = str(data.get("mode") or "live").strip().lower()
        row.mode = "test" if mode in ("test", "sandbox") else "live"
    if data.get("brand_name") is not None:
        row.brand_name = str(data.get("brand_name") or "Store").strip()[:120] or "Store"
    _set_enc(row, "enc_paypal_client_id", data.get("paypal_client_id"))
    _set_enc(row, "enc_paypal_secret", data.get("paypal_secret"))
    _set_enc(row, "enc_paypal_sandbox_client_id", data.get("paypal_sandbox_client_id"))
    _set_enc(row, "enc_paypal_sandbox_secret", data.get("paypal_sandbox_secret"))
    _set_enc(row, "enc_modem_public_key", data.get("modem_public_key"))
    _set_enc(row, "enc_modem_secret", data.get("modem_secret"))
    _set_enc(row, "enc_modem_webhook_secret", data.get("modem_webhook_secret"))
    _set_enc(row, "enc_modem_test_secret", data.get("modem_test_secret"))
    db.session.commit()
    return settings_public_dict()


def ping_paypal():
    from services.payment.paypal_provider import ping_credentials

    return ping_credentials()


def ping_modem():
    from services.payment.modempay_provider import ping_credentials

    return ping_credentials()
