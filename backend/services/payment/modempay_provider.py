"""Modem Pay provider integration."""

import json
import logging

logger = logging.getLogger(__name__)


def _modem_creds():
    from services.payment_settings_service import get_active_credentials

    return get_active_credentials()


def _modem_client():
    secret = (_modem_creds().get("modem_secret_key") or "").strip()
    if not secret:
        raise ValueError("Wave / AfriMoney / QMoney is not configured. Add the Modem Pay secret on the Payments page.")
    try:
        from modempay import ModemPay

        return ModemPay(api_key=secret)
    except ImportError:
        raise ValueError("Modem Pay SDK is not installed.")


def _major_amount(amount_cents, currency=None):
    """Whole dalasi (or whole units) — Modem Pay rejects fractional amounts."""
    from services.payment.fx_gmd import quote_gmd

    return int(quote_gmd(amount_cents, currency or "USD")["amount"])


def _stringify_metadata(metadata):
    out = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[str(key)] = "true" if value else "false"
        elif isinstance(value, (dict, list)):
            out[str(key)] = json.dumps(value)
        else:
            out[str(key)] = str(value)
    return out


def _as_dict(result):
    if isinstance(result, dict):
        return result
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return {"data": data, "message": getattr(result, "message", "")}
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    return {}


def _modem_error_text(exc):
    raw = exc.args[0] if getattr(exc, "args", None) else str(exc)
    if isinstance(raw, dict):
        nested = raw.get("message") or raw.get("error") or raw.get("errors")
        if isinstance(nested, (dict, list)):
            return json.dumps(nested)
        if nested:
            return str(nested)
        return json.dumps(raw)
    text = str(raw).strip()
    if text.startswith("ModemPayError:"):
        return text
    return text or "Modem Pay could not start this payment."


def create_payment_intent(amount_cents, currency, title, metadata, return_url, cancel_url, callback_url, customer=None, network=None):
    from services.payment.fx_gmd import quote_gmd

    client = _modem_client()
    customer = customer or {}
    quote = quote_gmd(amount_cents, currency)
    amount = int(quote["amount"])
    meta = dict(metadata or {})
    meta.update({
        "original_cents": quote["original_cents"],
        "original_currency": quote["original_currency"],
        "gmd_amount": amount,
        "usd_gmd_rate": quote["rate"],
    })
    params = {
        "amount": amount,
        "currency": "GMD",
        "title": (title or "Payment")[:120],
        "metadata": _stringify_metadata(meta),
        "payment_methods": ["wallet"],
    }
    if return_url:
        params["return_url"] = return_url
    if cancel_url:
        params["cancel_url"] = cancel_url
    # Never point the webhook at GitHub Pages; Modem Pay 400s invalid callback URLs.
    if callback_url and "github.io" not in callback_url:
        params["callback_url"] = callback_url
    if customer.get("full_name") or customer.get("name"):
        params["customer_name"] = (customer.get("full_name") or customer.get("name") or "")[:120]
    if customer.get("email"):
        params["customer_email"] = customer["email"][:120]
    phone = str(customer.get("phone") or "").strip()
    if phone:
        params["customer_phone"] = phone[:32]
    net = (network or "").strip().lower()
    if net in ("wave", "afrimoney", "qmoney", "aps"):
        params["network"] = net
    try:
        result = client.payment_intents.create(params=params)
    except Exception as exc:
        if params.get("network"):
            logger.warning("Modem Pay create with network=%s failed, retrying without: %s", params.get("network"), exc)
            params.pop("network", None)
            try:
                result = client.payment_intents.create(params=params)
            except Exception as exc2:
                logger.warning(
                    "Modem Pay create failed amount=%s currency=%s return_url=%s callback_url=%s error=%s",
                    amount,
                    params.get("currency"),
                    return_url,
                    params.get("callback_url"),
                    exc2,
                )
                raise ValueError(_modem_error_text(exc2)) from exc2
        else:
            logger.warning(
                "Modem Pay create failed amount=%s currency=%s return_url=%s callback_url=%s error=%s",
                amount,
                params.get("currency"),
                return_url,
                params.get("callback_url"),
                exc,
            )
            raise ValueError(_modem_error_text(exc)) from exc
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
        secret = (_modem_creds().get("modem_secret_key") or "").strip()
    else:
        secret = (_modem_creds().get("modem_webhook_secret") or "").strip()
    if not secret:
        raise ValueError("Modem Pay webhook secret is not configured.")
    client = _modem_client()
    return client.webhooks.compose_event_details(payload, signature, secret)


def fetch_and_verify_payment(intent_secret):
    """Server-side status check when webhook is delayed."""
    import requests

    secret = (_modem_creds().get("modem_secret_key") or "").strip()
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


def ping_credentials():
    result = create_payment_intent(
        100,
        "GMD",
        "Admin key test",
        {"admin_test": "ping"},
        "",
        "",
        "",
    )
    return {
        "ok": True,
        "message": "Wave / AfriMoney / QMoney keys work. Open the test page to complete 1 GMD.",
        "payment_link": result.get("payment_link") or "",
    }
