"""Fulfillment after verified payment."""

import json
import logging
from datetime import datetime

from models import (
    db,
    CommunityMembership,
    Coupon,
    Order,
    Payment,
    StoreOrder,
)
from services.payment.inventory import finalize_stock, release_reserved_stock

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = frozenset({"succeeded", "manual_approved"})


def _store_order_for(payment):
    return StoreOrder.query.filter_by(payment_id=payment.id).first()


def _release_store_order_stock(store_order):
    if not store_order:
        return
    for item in store_order.items.all():
        if item.product:
            release_reserved_stock(item.product, item.quantity or 1)


def _fulfill_store_order(store_order):
    store_order.payment_status = "succeeded"
    store_order.order_status = "paid"
    digital = []
    for item in store_order.items.all():
        product = item.product
        if product:
            finalize_stock(product, item.quantity or 1)
            if item.product_type == "digital":
                digital.append({
                    "title": item.product_title,
                    "url": product.digital_delivery_url or "",
                    "text": product.digital_delivery_text or "",
                })
    store_order.digital_delivery_json = json.dumps(digital)
    if not store_order.requires_shipping:
        store_order.order_status = "delivered"
    else:
        store_order.order_status = "processing"
    store_order.updated_at = datetime.utcnow()


def mark_payment_failed(payment, reason=""):
    if payment.status in SUCCESS_STATUSES:
        return
    payment.status = "failed"
    payment.manual_review_note = (reason or "")[:2000]
    payment.updated_at = datetime.utcnow()
    order = Order.query.filter_by(payment_id=payment.id).first()
    if order:
        order.payment_status = "failed"
        order.order_status = "cancelled"
        if order.product:
            release_reserved_stock(order.product, order.quantity or 1)
    store_order = _store_order_for(payment)
    if store_order:
        _release_store_order_stock(store_order)
        store_order.payment_status = "failed"
        store_order.order_status = "cancelled"
    if payment.membership_id:
        m = CommunityMembership.query.get(payment.membership_id)
        if m and m.status == "pending_payment":
            m.status = "removed"
    db.session.commit()


def fulfill_payment(payment, provider_event_id=None):
    """Idempotent fulfillment for successful payments."""
    if payment.paid_at and payment.status in SUCCESS_STATUSES:
        return payment

    payment.status = "succeeded"
    payment.paid_at = datetime.utcnow()
    payment.updated_at = datetime.utcnow()
    if provider_event_id:
        payment.provider_payment_id = provider_event_id or payment.provider_payment_id

    if payment.coupon_id:
        coupon = Coupon.query.get(payment.coupon_id)
        if coupon:
            coupon.used_count = (coupon.used_count or 0) + 1

    if payment.payment_kind == "product_order":
        order = Order.query.filter_by(payment_id=payment.id).first()
        if order:
            order.payment_status = "succeeded"
            order.order_status = "paid"
            product = order.product
            if product:
                finalize_stock(product, order.quantity or 1)
                if order.product_type == "digital":
                    order.digital_delivery_url = product.digital_delivery_url or ""
                    order.digital_delivery_text = product.digital_delivery_text or ""
            order.updated_at = datetime.utcnow()

    elif payment.payment_kind == "store_order":
        store_order = _store_order_for(payment)
        if store_order:
            _fulfill_store_order(store_order)

    elif payment.payment_kind == "community_membership":
        m = CommunityMembership.query.get(payment.membership_id)
        if m:
            m.status = "active"
            m.payment_id = payment.id
            m.approved_at = datetime.utcnow()

    db.session.commit()
    logger.info("Payment fulfilled: %s", payment.payment_reference)
    return payment


def approve_manual_payment(payment, note=""):
    payment.manual_review_note = (note or "")[:2000]
    payment.reviewed_at = datetime.utcnow()
    db.session.flush()
    return fulfill_payment(payment)


def reject_manual_payment(payment, note=""):
    payment.status = "manual_rejected"
    payment.manual_review_note = (note or "")[:2000]
    payment.reviewed_at = datetime.utcnow()
    order = Order.query.filter_by(payment_id=payment.id).first()
    if order:
        order.payment_status = "failed"
        order.order_status = "cancelled"
        if order.product:
            release_reserved_stock(order.product, order.quantity or 1)
    store_order = _store_order_for(payment)
    if store_order:
        _release_store_order_stock(store_order)
        store_order.payment_status = "failed"
        store_order.order_status = "cancelled"
    if payment.membership_id:
        m = CommunityMembership.query.get(payment.membership_id)
        if m and m.status == "pending_payment":
            m.status = "removed"
    db.session.commit()
    return payment


def save_delivery_info(order, delivery_data):
    if not order:
        return
    order.delivery_json = json.dumps(delivery_data or {})
    if order.order_status == "paid":
        order.order_status = "processing"
    order.updated_at = datetime.utcnow()
    db.session.commit()
