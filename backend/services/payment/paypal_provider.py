"""PayPal Checkout integration (REST API v2)."""

import logging

import requests

logger = logging.getLogger(__name__)


def _paypal_creds():
    from services.payment_settings_service import get_active_credentials

    return get_active_credentials()


def _paypal_base():
    mode = (_paypal_creds().get("paypal_mode") or "live").lower()
    if mode == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


def _access_token():
    creds = _paypal_creds()
    client_id = (creds.get("paypal_client_id") or "").strip()
    secret = (creds.get("paypal_client_secret") or "").strip()
    if not client_id or not secret:
        raise ValueError("PayPal is not configured. Add Client ID and Secret on the Payments page.")
    resp = requests.post(
        f"{_paypal_base()}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if resp.status_code >= 400:
        logger.error("PayPal token error: %s", resp.text)
        raise ValueError("PayPal authentication failed.")
    return resp.json().get("access_token")


def _amount_string(cents, currency):
    if currency == "GMD":
        return str(int(cents))
    return f"{(cents or 0) / 100:.2f}"


def create_order(total_cents, currency, reference, return_url, cancel_url):
    token = _access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": reference,
                "custom_id": reference,
                "amount": {
                    "currency_code": currency or "USD",
                    "value": _amount_string(total_cents, currency),
                },
            }
        ],
        "application_context": {
            "brand_name": (_paypal_creds().get("brand_name") or "Store")[:127],
            "landing_page": "BILLING",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    resp = requests.post(
        f"{_paypal_base()}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        logger.error("PayPal create order error: %s", resp.text)
        raise ValueError("PayPal could not create checkout.")
    data = resp.json()
    approve = ""
    for link in data.get("links") or []:
        if link.get("rel") == "approve":
            approve = link.get("href") or ""
    return {
        "provider_payment_id": data.get("id") or "",
        "payment_link": approve,
    }


def capture_order(order_id):
    token = _access_token()
    resp = requests.post(
        f"{_paypal_base()}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        logger.error("PayPal capture error: %s", resp.text)
        return None
    return resp.json()


def get_order(order_id):
    token = _access_token()
    resp = requests.get(
        f"{_paypal_base()}/v2/checkout/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code >= 400:
        return None
    return resp.json()


def ping_credentials():
    token = _access_token()
    if not token:
        raise ValueError("PayPal did not return an access token.")
    mode = _paypal_creds().get("paypal_mode") or "live"
    return {"ok": True, "message": f"PayPal keys work ({mode} mode)."}
