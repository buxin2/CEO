"""Payment and order API routes."""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session

from models import Coupon, Community, CommunityMemberUser, Order, Payment, db
from routes.auth import login_required
from routes.community import community_member_required
from services.payment.checkout_service import (
    checkout_community_membership,
    checkout_product,
    get_checkout_preview,
    manual_payment_instructions,
    payment_by_reference,
    process_modem_webhook,
    start_admin_test_payment,
    paypal_sdk_config,
    verify_and_capture_payment,
)
from services.payment_settings_service import (
    ping_modem,
    ping_paypal,
    settings_public_dict,
    update_settings as update_payment_settings,
)
from services.payment.fulfillment import approve_manual_payment, reject_manual_payment, save_delivery_info

payments_bp = Blueprint("payments", __name__)


def _payment_response(payment, order=None):
    order_row = order or Order.query.filter_by(payment_id=payment.id).first()
    data = {
        "payment": payment.to_dict(include_private=True),
        "manual_instructions": manual_payment_instructions() if payment.provider == "manual" else None,
    }
    if order_row:
        data["order"] = order_row.to_dict(include_private=True)
    if payment.payment_kind == "store_order":
        from services.store_checkout import store_order_for_payment
        from utils import store_order_link

        store_order = store_order_for_payment(payment)
        if store_order:
            data["store_order"] = store_order.to_dict(include_private=True)
            data["order_url"] = store_order_link(store_order.order_number, store_order.access_token)
    return data


@payments_bp.route("/api/checkout/preview", methods=["GET"])
def api_checkout_preview():
    product_id = request.args.get("product_id", type=int)
    membership_id = request.args.get("membership_id", type=int)
    quantity = request.args.get("quantity", 1, type=int)
    coupon_code = request.args.get("coupon_code")
    member_id = session.get("cm_user_id")
    try:
        preview = get_checkout_preview(
            product_id=product_id,
            membership_id=membership_id,
            quantity=quantity,
            coupon_code=coupon_code,
            member_user_id=member_id,
        )
        return jsonify(preview)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/checkout/product", methods=["POST"])
@community_member_required
def api_checkout_product():
    data = request.get_json(silent=True) or {}
    try:
        payment, order = checkout_product(
            session.get("cm_user_id"),
            data.get("product_id"),
            data.get("quantity", 1),
            data.get("coupon_code"),
            data.get("payment_method"),
            customer_info=data.get("customer") or {},
            wallet_network=data.get("wallet_network"),
        )
        return jsonify(_payment_response(payment, order)), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/checkout/membership", methods=["POST"])
@community_member_required
def api_checkout_membership():
    data = request.get_json(silent=True) or {}
    try:
        payment, _ = checkout_community_membership(
            session.get("cm_user_id"),
            data.get("membership_id"),
            data.get("coupon_code"),
            data.get("payment_method"),
            customer_info=data.get("customer") or {},
            wallet_network=data.get("wallet_network"),
        )
        return jsonify(_payment_response(payment)), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/checkout/verify/<payment_ref>", methods=["POST"])
def api_verify_payment(payment_ref):
    data = request.get_json(silent=True) or {}
    try:
        payment = verify_and_capture_payment(payment_ref, paypal_order_id=data.get("paypal_order_id"))
        order = Order.query.filter_by(payment_id=payment.id).first()
        return jsonify(_payment_response(payment, order))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/checkout/payment/<payment_ref>", methods=["GET"])
def api_get_payment(payment_ref):
    payment = payment_by_reference(payment_ref)
    if not payment:
        return jsonify({"error": "Payment not found."}), 404
    member_id = session.get("cm_user_id")
    if member_id and payment.member_user_id != member_id:
        return jsonify({"error": "Not allowed."}), 403
    order = Order.query.filter_by(payment_id=payment.id).first()
    return jsonify(_payment_response(payment, order))


@payments_bp.route("/api/checkout/receipt/<payment_ref>", methods=["POST"])
@community_member_required
def api_upload_receipt(payment_ref):
    payment = payment_by_reference(payment_ref)
    if not payment or payment.member_user_id != session.get("cm_user_id"):
        return jsonify({"error": "Payment not found."}), 404
    if payment.provider != "manual":
        return jsonify({"error": "This payment does not accept manual receipts."}), 400

    receipt_url = (request.form.get("receipt_url") or "").strip()
    if request.files.get("receipt"):
        from services.cloudinary_service import upload_payment_receipt

        try:
            result = upload_payment_receipt(request.files["receipt"], payment.id)
            receipt_url = result.get("url") or receipt_url
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400

    if not receipt_url:
        return jsonify({"error": "Receipt URL or file is required."}), 400

    payment.receipt_url = receipt_url[:500]
    payment.status = "manual_pending"
    db.session.commit()
    order = Order.query.filter_by(payment_id=payment.id).first()
    return jsonify(_payment_response(payment, order))


@payments_bp.route("/api/checkout/delivery/<order_number>", methods=["POST"])
@community_member_required
def api_save_delivery(order_number):
    order = Order.query.filter_by(order_number=order_number).first()
    if not order or order.member_user_id != session.get("cm_user_id"):
        return jsonify({"error": "Order not found."}), 404
    data = request.get_json(silent=True) or {}
    save_delivery_info(order, data.get("delivery") or data)
    return jsonify(order.to_dict(include_private=True))


@payments_bp.route("/api/webhooks/modempay", methods=["POST"])
def api_modem_webhook():
    signature = request.headers.get("x-modem-signature") or ""
    payload = request.get_json(silent=True) or {}
    try:
        result = process_modem_webhook(payload, signature, use_secret_key=False)
        return jsonify(result)
    except Exception as exc:
        current_app.logger.warning("Modem webhook error: %s", exc)
        return jsonify({"error": "Invalid webhook"}), 400


@payments_bp.route("/api/webhooks/modempay/callback", methods=["POST"])
def api_modem_callback():
    signature = request.headers.get("x-modem-signature") or ""
    payload = request.get_json(silent=True) or {}
    try:
        result = process_modem_webhook(payload, signature, use_secret_key=True)
        return jsonify(result)
    except Exception as exc:
        current_app.logger.warning("Modem callback error: %s", exc)
        return jsonify({"error": "Invalid callback"}), 400


# ---------- Admin ----------


@payments_bp.route("/api/admin/payment-settings", methods=["GET"])
@login_required
def api_admin_payment_settings():
    return jsonify(settings_public_dict())


@payments_bp.route("/api/admin/payment-settings", methods=["PUT"])
@login_required
def api_admin_payment_settings_update():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(update_payment_settings(data))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/admin/payment-settings/ping", methods=["POST"])
@login_required
def api_admin_payment_ping():
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "").strip().lower()
    try:
        if provider == "paypal":
            return jsonify(ping_paypal())
        if provider == "modem":
            return jsonify(ping_modem())
        raise ValueError("Choose paypal or modem.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/admin/payments/test", methods=["POST"])
@login_required
def api_admin_payment_test():
    data = request.get_json(silent=True) or {}
    admin = None
    if session.get("admin_id"):
        from models import Admin

        admin = Admin.query.get(session["admin_id"])
    try:
        payment = start_admin_test_payment(data.get("provider"), admin.email if admin else "")
        return jsonify({
            "payment": payment.to_dict(include_private=True),
            "paypal_sdk": paypal_sdk_config(payment.currency) if payment.provider == "paypal" else None,
        }), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@payments_bp.route("/api/admin/payments", methods=["GET"])
@login_required
def api_admin_payments():
    q = Payment.query.order_by(Payment.created_at.desc())
    status = request.args.get("status")
    provider = request.args.get("provider")
    community_id = request.args.get("community_id", type=int)
    if status:
        q = q.filter(Payment.status == status)
    if provider:
        q = q.filter(Payment.provider == provider)
    if community_id:
        q = q.filter(Payment.community_id == community_id)

    rows = q.limit(500).all()
    summary = {
        "total": len(rows),
        "succeeded": sum(1 for p in rows if p.status == "succeeded"),
        "pending": sum(1 for p in rows if p.status in ("pending", "processing", "manual_pending")),
        "failed": sum(1 for p in rows if p.status in ("failed", "manual_rejected")),
        "revenue_cents": sum(p.total_cents or 0 for p in rows if p.status == "succeeded"),
        "manual_pending": sum(1 for p in rows if p.status == "manual_pending"),
    }
    return jsonify({
        "summary": summary,
        "payments": [p.to_dict(include_private=True) for p in rows],
    })


@payments_bp.route("/api/admin/payments/<int:payment_id>/approve", methods=["POST"])
@login_required
def api_admin_approve_payment(payment_id):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "Payment not found."}), 404
    data = request.get_json(silent=True) or {}
    payment = approve_manual_payment(payment, note=data.get("note") or "")
    order = Order.query.filter_by(payment_id=payment.id).first()
    return jsonify(_payment_response(payment, order))


@payments_bp.route("/api/admin/payments/<int:payment_id>/reject", methods=["POST"])
@login_required
def api_admin_reject_payment(payment_id):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({"error": "Payment not found."}), 404
    data = request.get_json(silent=True) or {}
    payment = reject_manual_payment(payment, note=data.get("note") or "")
    order = Order.query.filter_by(payment_id=payment.id).first()
    return jsonify(_payment_response(payment, order))


@payments_bp.route("/api/admin/orders", methods=["GET"])
@login_required
def api_admin_orders():
    q = Order.query.order_by(Order.created_at.desc())
    community_id = request.args.get("community_id", type=int)
    if community_id:
        q = q.filter(Order.community_id == community_id)
    rows = q.limit(500).all()
    return jsonify({"orders": [o.to_dict(include_private=True) for o in rows]})


@payments_bp.route("/api/admin/orders/<int:order_id>", methods=["PUT"])
@login_required
def api_admin_update_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    data = request.get_json(silent=True) or {}
    if data.get("order_status"):
        order.order_status = str(data["order_status"]).strip()[:30]
    order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(order.to_dict(include_private=True))


@payments_bp.route("/api/admin/coupons", methods=["GET"])
@login_required
def api_admin_coupons_list():
    rows = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return jsonify({"coupons": [c.to_dict() for c in rows]})


@payments_bp.route("/api/admin/coupons", methods=["POST"])
@login_required
def api_admin_coupons_create():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify({"error": "Coupon code is required."}), 400
    if Coupon.query.filter_by(code=code).first():
        return jsonify({"error": "Coupon code already exists."}), 400
    coupon = Coupon(
        code=code,
        discount_type=(data.get("discount_type") or "percent")[:20],
        discount_value=int(data.get("discount_value") or 0),
        max_uses=data.get("max_uses"),
        is_active=bool(data.get("is_active", True)),
        applies_to=(data.get("applies_to") or "all")[:20],
        community_id=data.get("community_id"),
        community_product_id=data.get("community_product_id"),
        store_product_id=data.get("store_product_id"),
    )
    if data.get("expires_at"):
        try:
            coupon.expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", ""))
        except ValueError:
            pass
    db.session.add(coupon)
    db.session.commit()
    return jsonify(coupon.to_dict()), 201


@payments_bp.route("/api/admin/coupons/<int:coupon_id>", methods=["PUT"])
@login_required
def api_admin_coupons_update(coupon_id):
    coupon = Coupon.query.get(coupon_id)
    if not coupon:
        return jsonify({"error": "Coupon not found."}), 404
    data = request.get_json(silent=True) or {}
    for field in ("discount_type", "applies_to"):
        if data.get(field) is not None:
            setattr(coupon, field, str(data[field])[:20])
    if data.get("discount_value") is not None:
        coupon.discount_value = int(data["discount_value"])
    if data.get("max_uses") is not None:
        coupon.max_uses = data["max_uses"]
        if data.get("is_active") is not None:
            coupon.is_active = bool(data["is_active"])
    if "store_product_id" in data:
        coupon.store_product_id = data.get("store_product_id")
    db.session.commit()
    return jsonify(coupon.to_dict())
