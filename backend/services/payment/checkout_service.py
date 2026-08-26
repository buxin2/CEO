"""Checkout orchestration — create payments and provider sessions."""

import json
import logging
from datetime import datetime

from flask import current_app

from models import (
    db,
    Community,
    CommunityMembership,
    CommunityMemberUser,
    CommunityProduct,
    Order,
    Payment,
    PaymentWebhookEvent,
)
from services.payment.fulfillment import fulfill_payment, mark_payment_failed
from services.payment.inventory import lock_product, reserve_stock, InventoryError
from services.payment.money import generate_reference
from services.payment.modempay_provider import create_payment_intent, verify_webhook
from services.payment.paypal_provider import capture_order, create_order as paypal_create_order
from services.payment.pricing import calculate_community_totals, calculate_product_totals

logger = logging.getLogger(__name__)


def _frontend_url(path):
    base = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _backend_url(path):
    # Render backend URL for webhooks — never fall back to GitHub Pages.
    backend = (
        current_app.config.get("BACKEND_URL")
        or current_app.config.get("RENDER_EXTERNAL_URL")
        or ""
    ).rstrip("/")
    if not backend:
        return ""
    return f"{backend}/{path.lstrip('/')}"


def manual_payment_instructions():
    return current_app.config.get("MANUAL_PAYMENT_INSTRUCTIONS") or {}


def get_payment_methods(currency):
    methods = []
    if (current_app.config.get("MODEMPAY_SECRET_KEY") or "").strip():
        methods.append({"id": "modem", "label": "Modem Pay (Mobile Wallet)", "currencies": ["GMD", "USD"]})
    if (current_app.config.get("PAYPAL_CLIENT_ID") or "").strip():
        methods.append({"id": "paypal", "label": "PayPal", "currencies": ["USD", "EUR", "GBP"]})
    methods.append({"id": "manual", "label": "Bank / Money Transfer", "currencies": ["USD", "GMD"]})
    cur = (currency or "USD").upper()
    return [m for m in methods if cur in m["currencies"] or m["id"] == "manual"]


def _create_payment_record(
    payment_kind,
    totals,
    member_user,
    community_id,
    community_product_id=None,
    membership_id=None,
    provider="manual",
    customer_info=None,
):
    customer_info = customer_info or {}
    payment = Payment(
        payment_reference=generate_reference("PAY"),
        payment_kind=payment_kind,
        membership_id=membership_id,
        community_id=community_id,
        community_product_id=community_product_id,
        member_user_id=member_user.id if member_user else None,
        subtotal_cents=totals.get("subtotal_cents", 0),
        discount_cents=totals.get("discount_cents", 0),
        fee_cents=totals.get("fee_cents", 0),
        total_cents=totals.get("total_cents", 0),
        currency=totals.get("currency", "USD"),
        provider=provider,
        status="pending",
        coupon_id=totals.get("coupon").id if totals.get("coupon") else None,
        customer_name=(customer_info.get("full_name") or (member_user.full_name if member_user else "") or "")[:255],
        customer_email=(customer_info.get("email") or (member_user.email if member_user else "") or "")[:255],
        customer_phone=(customer_info.get("phone") or "")[:64],
    )
    db.session.add(payment)
    db.session.flush()
    return payment


def _init_provider_session(payment, title, metadata, return_path=None, cancel_path=None):
    ref = payment.payment_reference
    return_url = _frontend_url(return_path or f"checkout.html?payment_ref={ref}&status=return")
    cancel_url = _frontend_url(cancel_path or f"checkout.html?payment_ref={ref}&status=cancel")
    callback_url = _backend_url("api/webhooks/modempay/callback")

    if payment.provider == "modem":
        result = create_payment_intent(
            payment.total_cents,
            payment.currency,
            title,
            metadata,
            return_url,
            cancel_url,
            callback_url,
            customer={
                "full_name": payment.customer_name,
                "email": payment.customer_email,
                "phone": payment.customer_phone,
            },
        )
        payment.provider_payment_id = result.get("provider_payment_id") or ""
        payment.provider_intent_secret = result.get("provider_intent_secret") or ""
        payment.payment_link = result.get("payment_link") or ""
        if not payment.payment_link:
            raise ValueError("Modem Pay did not return a payment page. Please try PayPal or bank transfer.")
        payment.status = "processing"
    elif payment.provider == "paypal":
        result = paypal_create_order(
            payment.total_cents,
            payment.currency,
            ref,
            return_url,
            cancel_url,
        )
        payment.provider_payment_id = result.get("provider_payment_id") or ""
        payment.payment_link = result.get("payment_link") or ""
        payment.status = "processing"
    elif payment.provider == "manual":
        payment.status = "manual_pending"
    elif payment.provider == "coupon":
        payment.status = "pending"

    db.session.flush()
    return payment


def checkout_product(member_user_id, product_id, quantity, coupon_code, payment_method, customer_info=None):
    member = CommunityMemberUser.query.get(member_user_id)
    if not member:
        raise ValueError("Please log in to purchase.")

    product = lock_product(product_id)
    if not product:
        raise ValueError("Product not found.")
    if product.effective_status() in ("unavailable", "out_of_stock"):
        raise ValueError("This product is not available.")

    qty = max(1, int(quantity or 1))
    try:
        reserve_stock(product, qty)
    except InventoryError as exc:
        raise ValueError(str(exc))

    totals = calculate_product_totals(product, qty, coupon_code)
    totals["coupon_obj"] = totals.get("coupon")
    if totals.get("coupon"):
        totals["coupon"] = totals["coupon"]  # keep for _create_payment_record

    provider = (payment_method or "manual").lower()
    if totals["total_cents"] <= 0:
        provider = "coupon"

    payment = _create_payment_record(
        "product_order",
        totals,
        member,
        product.community_id,
        community_product_id=product.id,
        provider=provider,
        customer_info=customer_info,
    )

    order = Order(
        order_number=generate_reference("ORD"),
        community_id=product.community_id,
        community_product_id=product.id,
        member_user_id=member.id,
        payment_id=payment.id,
        quantity=qty,
        unit_price_cents=totals["unit_price_cents"],
        subtotal_cents=totals["subtotal_cents"],
        discount_cents=totals["discount_cents"],
        total_cents=totals["total_cents"],
        currency=totals["currency"],
        payment_status="pending",
        order_status="pending_payment",
        product_type=product.product_type or "physical",
    )
    db.session.add(order)
    db.session.flush()

    if totals["total_cents"] <= 0:
        fulfill_payment(payment)
        return payment, order

    payment = _init_provider_session(
        payment,
        product.name,
        {"payment_reference": payment.payment_reference, "product_id": product.id},
    )
    db.session.commit()
    return payment, order


def checkout_community_membership(member_user_id, membership_id, coupon_code, payment_method, customer_info=None):
    member = CommunityMemberUser.query.get(member_user_id)
    if not member:
        raise ValueError("Please log in to continue.")

    membership = CommunityMembership.query.get(membership_id)
    if not membership or membership.member_user_id != member.id:
        raise ValueError("Membership not found.")
    if membership.status != "pending_payment":
        raise ValueError("This membership does not require payment.")

    community = Community.query.get(membership.community_id)
    if not community:
        raise ValueError("Community not found.")

    totals = calculate_community_totals(community, coupon_code)
    provider = (payment_method or "manual").lower()
    if totals["total_cents"] <= 0:
        provider = "coupon"

    payment = _create_payment_record(
        "community_membership",
        totals,
        member,
        community.id,
        membership_id=membership.id,
        provider=provider,
        customer_info=customer_info,
    )

    if totals["total_cents"] <= 0:
        fulfill_payment(payment)
        return payment, None

    payment = _init_provider_session(
        payment,
        f"{community.name} membership",
        {"payment_reference": payment.payment_reference, "membership_id": membership.id},
    )
    db.session.commit()
    return payment, None


def get_checkout_preview(product_id=None, membership_id=None, quantity=1, coupon_code=None, member_user_id=None):
    if product_id:
        product = CommunityProduct.query.get(product_id)
        if not product:
            raise ValueError("Product not found.")
        totals = calculate_product_totals(product, quantity, coupon_code)
        return {
            "kind": "product",
            "product": product.to_dict(),
            "totals": {k: totals[k] for k in ("quantity", "unit_price_cents", "subtotal_cents", "fee_cents", "discount_cents", "total_cents", "currency")},
            "payment_methods": get_payment_methods(totals["currency"]),
        }
    if membership_id:
        membership = CommunityMembership.query.get(membership_id)
        if not membership:
            raise ValueError("Membership not found.")
        if member_user_id and membership.member_user_id != member_user_id:
            raise ValueError("Membership not found.")
        community = Community.query.get(membership.community_id)
        totals = calculate_community_totals(community, coupon_code)
        return {
            "kind": "membership",
            "community": community.to_dict(),
            "membership_id": membership.id,
            "totals": {k: totals[k] for k in ("subtotal_cents", "fee_cents", "discount_cents", "total_cents", "currency")},
            "payment_methods": get_payment_methods(totals["currency"]),
        }
    raise ValueError("product_id or membership_id required.")


def verify_and_capture_payment(payment_ref, paypal_order_id=None):
    payment = Payment.query.filter_by(payment_reference=payment_ref).first()
    if not payment:
        raise ValueError("Payment not found.")
    if payment.paid_at:
        return payment

    if payment.provider == "paypal" and paypal_order_id:
        capture = capture_order(paypal_order_id or payment.provider_payment_id)
        if capture and capture.get("status") == "COMPLETED":
            return fulfill_payment(payment, provider_event_id=paypal_order_id)
        mark_payment_failed(payment, "PayPal capture was not completed.")
        return payment

    if payment.provider == "modem" and payment.provider_intent_secret:
        from services.payment.modempay_provider import fetch_and_verify_payment

        data = fetch_and_verify_payment(payment.provider_intent_secret)
        if data and str(data.get("status")).lower() in ("succeeded", "completed", "paid"):
            return fulfill_payment(payment)

    return payment


def process_modem_webhook(payload, signature, use_secret_key=False):
    event = verify_webhook(payload, signature, use_secret_key=use_secret_key)
    event_type = event.get("event") if isinstance(event, dict) else getattr(event, "event", "")
    payload_data = event.get("payload") if isinstance(event, dict) else getattr(event, "payload", {})
    event_key = f"{event_type}:{payload_data.get('id') or payload_data.get('intent_secret') or ''}"

    existing = PaymentWebhookEvent.query.filter_by(provider="modem", event_key=event_key).first()
    if existing:
        return {"duplicate": True}

    payment = None
    meta_ref = None
    if isinstance(payload_data, dict):
        meta = payload_data.get("metadata") or {}
        meta_ref = meta.get("payment_reference")
        if meta_ref:
            payment = Payment.query.filter_by(payment_reference=meta_ref).first()
        if not payment and payload_data.get("intent_secret"):
            payment = Payment.query.filter_by(provider_intent_secret=payload_data["intent_secret"]).first()

    row = PaymentWebhookEvent(
        provider="modem",
        event_key=event_key or generate_reference("WH"),
        payment_id=payment.id if payment else None,
        payload_json=json.dumps(payload_data or {}),
    )
    db.session.add(row)

    if payment and event_type in ("charge.succeeded", "payment_intent.succeeded"):
        fulfill_payment(payment, provider_event_id=payload_data.get("id"))
    db.session.commit()
    return {"processed": True, "event": event_type}


def payment_by_reference(ref):
    return Payment.query.filter_by(payment_reference=ref).first()
