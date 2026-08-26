"""Modem Pay provider integration."""

import logging

from flask import current_app

logger = logging.getLogger(__name__)


def _modem_client():
    secret = (current_app.config.get("MODEMPAY_SECRET_KEY") or "").strip()
    if not secret:
        raise ValueError("Modem Pay is not configured on the server.")
    try:
        from modempay import ModemPay

        return ModemPay(api_key=secret)
    except ImportError:
        raise ValueError("Modem Pay SDK is not installed.")


def _major_amount(amount_cents, currency):
    """Modem Pay amount is in major units (GMD 450, USD 34.99), not cents."""
    major = max(0, int(amount_cents or 0)) / 100.0
    cur = (currency or "USD").upper()
    if cur in ("GMD", "JPY", "KRW", "VND"):
        return max(1, int(round(major)))
    value = round(major, 2)
    return value if value >= 0.5 else 0.5


def _as_dict(result):
    if isinstance(result, dict):
        return result
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return {"data": data, "message": getattr(result, "message", "")}
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    return {}


def create_payment_intent(amount_cents, currency, title, metadata, return_url, cancel_url, callback_url, customer=None):
    client = _modem_client()
    customer = customer or {}
    amount = _major_amount(amount_cents, currency)
    params = {
        "amount": amount,
        "currency": (currency or "USD").upper(),
        "title": (title or "Payment")[:120],
        "metadata": metadata or {},
        "return_url": return_url,
        "cancel_url": cancel_url,
        "callback_url": callback_url,
        "from_sdk": False,
        "skip_url_validation": True,
    }
    if customer.get("full_name") or customer.get("name"):
        params["customer_name"] = (customer.get("full_name") or customer.get("name") or "")[:120]
    if customer.get("email"):
        params["customer_email"] = customer["email"][:120]
    if customer.get("phone"):
        params["customer_phone"] = str(customer["phone"])[:32]
    try:
        result = client.payment_intents.create(params=params)
    except Exception as exc:
        logger.warning("Modem Pay create failed: %s", exc)
        raise ValueError("Modem Pay could not start this payment. Please try PayPal or bank transfer.")
    body = _as_dict(result)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    link = data.get("payment_link") or body.get("payment_link") or ""
    if not link:
        logger.warning("Modem Pay returned no payment_link: %s", str(body)[:500])
        msg = body.get("message") or data.get("message") or "Modem Pay did not return a payment page."
        raise ValueError(str(msg))
    return {
        "provider_payment_id": data.get("intent_secret") or data.get("id") or "",
        "provider_intent_secret": data.get("intent_secret") or "",
        "payment_link": link,
    }


def verify_webhook(payload, signature, use_secret_key=False):
    """Verify global webhook (webhook secret) or callback (merchant secret)."""
    if use_secret_key:
        secret = (current_app.config.get("MODEMPAY_SECRET_KEY") or "").strip()
    else:
        secret = (current_app.config.get("MODEMPAY_WEBHOOK_SECRET") or "").strip()
    if not secret:
        raise ValueError("Modem Pay webhook secret is not configured.")
    client = _modem_client()
    return client.webhooks.compose_event_details(payload, signature, secret)


def fetch_and_verify_payment(intent_secret):
    """Server-side status check when webhook is delayed."""
    import requests

    secret = (current_app.config.get("MODEMPAY_SECRET_KEY") or "").strip()
    if not secret or not intent_secret:
        return None
    try:
        resp = requests.get(
            f"https://api.modempay.com/v1/payments/{intent_secret}",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            return body.get("data") or body
    except Exception as exc:
        logger.warning("Modem Pay status check failed: %s", exc)
    return None
