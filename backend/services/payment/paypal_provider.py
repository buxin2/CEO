"""PayPal Checkout integration (REST API v2)."""

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _paypal_base():
    mode = (current_app.config.get("PAYPAL_MODE") or "live").lower()
    if mode == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


def _access_token():
    client_id = (current_app.config.get("PAYPAL_CLIENT_ID") or "").strip()
    secret = (current_app.config.get("PAYPAL_CLIENT_SECRET") or "").strip()
    if not client_id or not secret:
        raise ValueError("PayPal is not configured on the server.")
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
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
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
