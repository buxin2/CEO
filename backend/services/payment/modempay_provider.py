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


def create_payment_intent(amount_cents, currency, title, metadata, return_url, cancel_url, callback_url):
    client = _modem_client()
    amount = max(1, int(amount_cents))
    params = {
        "amount": amount,
        "currency": currency or "GMD",
        "title": title[:120] if title else "Payment",
        "metadata": metadata or {},
        "return_url": return_url,
        "cancel_url": cancel_url,
        "callback_url": callback_url,
        "from_sdk": False,
    }
    result = client.payment_intents.create(params=params)
    data = result.get("data") if isinstance(result, dict) else {}
    if not data:
        raise ValueError("Modem Pay did not return payment data.")
    return {
        "provider_payment_id": data.get("intent_secret") or data.get("id") or "",
        "provider_intent_secret": data.get("intent_secret") or "",
        "payment_link": data.get("payment_link") or "",
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
