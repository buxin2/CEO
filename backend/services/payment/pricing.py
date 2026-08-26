"""Backend price calculation — never trust frontend totals."""

from datetime import datetime

from models import Coupon, Community, CommunityProduct
from services.payment.money import parse_price_to_cents


def _coupon_error(msg):
    raise ValueError(msg)


def validate_and_apply_coupon(code, subtotal_cents, applies_context):
    """Return (discount_cents, coupon) for a valid coupon code."""
    if not code:
        return 0, None
    coupon = Coupon.query.filter_by(code=str(code).strip().upper()).first()
    if not coupon or not coupon.is_active:
        _coupon_error("Coupon code is invalid.")
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        _coupon_error("Coupon has expired.")
    if coupon.max_uses is not None and (coupon.used_count or 0) >= coupon.max_uses:
        _coupon_error("Coupon usage limit reached.")

    applies = coupon.applies_to or "all"
    if applies == "product":
        pid = applies_context.get("community_product_id")
        if not pid or coupon.community_product_id != pid:
            _coupon_error("Coupon does not apply to this product.")
    elif applies == "community":
        cid = applies_context.get("community_id")
        if not cid or coupon.community_id != cid:
            _coupon_error("Coupon does not apply to this community.")
    elif applies in ("store", "store_product"):
        if not applies_context.get("store"):
            _coupon_error("Coupon does not apply to this order.")
        if applies == "store_product":
            pids = applies_context.get("store_product_ids") or []
            if not coupon.store_product_id or coupon.store_product_id not in pids:
                _coupon_error("Coupon does not apply to this product.")
    elif applies == "all":
        pass
    else:
        if applies_context.get("store") and applies not in ("all", "store", "store_product"):
            _coupon_error("Coupon does not apply to store orders.")

    discount = 0
    if coupon.discount_type == "percent":
        pct = min(100, max(0, coupon.discount_value or 0))
        discount = int(round(subtotal_cents * pct / 100))
    else:
        discount = min(subtotal_cents, coupon.discount_value or 0)
    return discount, coupon


def calculate_product_totals(product, quantity, coupon_code=None):
    product = product  # CommunityProduct
    qty = max(1, int(quantity or 1))
    unit_cents = product.price_cents or 0
    if unit_cents <= 0:
        unit_cents = parse_price_to_cents(product.price)
    subtotal = unit_cents * qty
    fee_cents = 0
    if product.fee_percent and product.fee_percent > 0:
        fee_cents = int(round(subtotal * product.fee_percent / 100))
    discount_cents, coupon = validate_and_apply_coupon(
        coupon_code,
        subtotal + fee_cents,
        {"community_product_id": product.id, "community_id": product.community_id},
    )
    total = max(0, subtotal + fee_cents - discount_cents)
    return {
        "quantity": qty,
        "unit_price_cents": unit_cents,
        "subtotal_cents": subtotal,
        "fee_cents": fee_cents,
        "discount_cents": discount_cents,
        "total_cents": total,
        "currency": product.currency or "USD",
        "coupon": coupon,
    }


def calculate_community_totals(community, coupon_code=None):
    if (community.community_type or "free") != "paid":
        _coupon_error("This community does not require payment.")
    subtotal = community.price_cents or 0
    if subtotal <= 0:
        _coupon_error("Community price is not configured.")
    discount_cents, coupon = validate_and_apply_coupon(
        coupon_code,
        subtotal,
        {"community_id": community.id},
    )
    total = max(0, subtotal - discount_cents)
    return {
        "subtotal_cents": subtotal,
        "fee_cents": 0,
        "discount_cents": discount_cents,
        "total_cents": total,
        "currency": community.currency or "USD",
        "coupon": coupon,
    }


def calculate_store_line(product, quantity, selected_options):
    """selected_options: {option_name: value_label}"""
    qty = int(quantity or 0)
    if qty < 1:
        raise ValueError("Quantity must be at least 1.")
    extra = 0
    normalized = {}
    options = list(product.options.all())
    incoming = selected_options or {}
    if options:
        for opt in options:
            values = [v for v in opt.values.all() if (v.label or "").strip()]
            if not values:
                continue
            wanted = incoming.get(opt.name) or incoming.get(str(opt.id))
            if not wanted:
                raise ValueError(f"Please choose a {opt.name}.")
            match = None
            for val in values:
                if val.label.lower() == str(wanted).strip().lower() or str(val.id) == str(wanted):
                    match = val
                    break
            if not match:
                raise ValueError(f"Invalid {opt.name} selection.")
            extra += match.extra_cents or 0
            normalized[opt.name] = match.label
    unit = product.unit_price_cents() + extra
    return {
        "product": product,
        "quantity": qty,
        "unit_price_cents": product.unit_price_cents(),
        "extra_cents": extra,
        "line_total_cents": unit * qty,
        "options": normalized,
        "currency": product.currency or "USD",
    }
