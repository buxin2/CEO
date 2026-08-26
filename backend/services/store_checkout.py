"""Guest-capable store checkout using the existing payment providers."""

import json

from models import db, StoreOrder, StoreOrderItem, StoreProduct, generate_token
from services.payment.checkout_service import (
    _create_payment_record,
    _init_provider_session,
    get_payment_methods,
)
from services.payment.fulfillment import fulfill_payment
from services.payment.inventory import InventoryError, lock_store_product, reserve_stock
from services.payment.money import generate_reference
from services.payment.pricing import calculate_store_line, validate_and_apply_coupon
from services.store_shipping import ShippingUnavailable, calculate_shipping, list_enabled_countries


def _email_ok(email):
    email = (email or "").strip()
    return "@" in email and "." in email.split("@")[-1]


def _line_items_from_request(items):
    if not items:
        raise ValueError("Cart is empty.")
    lines = []
    currency = None
    for raw in items:
        pid = raw.get("product_id")
        qty = int(raw.get("quantity") or 1)
        if qty < 1:
            raise ValueError("Quantity must be at least 1.")
        product = StoreProduct.query.get(pid)
        if not product or not product.is_public():
            raise ValueError("One of the products is not available.")
        if product.sellable_quantity() is not None and product.sellable_quantity() <= 0:
            raise ValueError(f"{product.title} is out of stock.")
        line = calculate_store_line(product, qty, raw.get("options") or {})
        if currency and line["currency"] != currency:
            raise ValueError("All products in the cart must use the same currency.")
        currency = line["currency"]
        lines.append(line)
    return lines


def preview_store_checkout(items, coupon_code=None, country=None, region=None):
    lines = _line_items_from_request(items)
    subtotal = sum(l["line_total_cents"] for l in lines)
    products = [l["product"] for l in lines]
    discount_cents, coupon = validate_and_apply_coupon(
        coupon_code,
        subtotal,
        {
            "store": True,
            "store_product_ids": [p.id for p in products],
        },
    )
    after_discount = max(0, subtotal - discount_cents)
    shipping = {
        "shipping_cents": 0,
        "requires_shipping": any(
            (p.product_type or "physical") != "digital" and p.shipping_required for p in products
        ),
        "note": "",
        "available": True,
    }
    if shipping["requires_shipping"] and country:
        try:
            ship = calculate_shipping(country, region, after_discount, products)
            shipping = {
                "shipping_cents": ship["shipping_cents"],
                "requires_shipping": True,
                "note": ship.get("note") or "",
                "available": True,
                "free_shipping": ship.get("free_shipping"),
            }
        except ShippingUnavailable as exc:
            shipping = {
                "shipping_cents": 0,
                "requires_shipping": True,
                "note": str(exc),
                "available": False,
            }
    elif shipping["requires_shipping"] and not country:
        shipping["note"] = "Select a country to calculate shipping."
        shipping["available"] = None

    total = after_discount + (shipping["shipping_cents"] if shipping.get("available") else 0)
    currency = lines[0]["currency"]
    return {
        "kind": "store",
        "items": [
            {
                "product_id": l["product"].id,
                "title": l["product"].title,
                "slug": l["product"].slug,
                "cover_image": (l["product"].images.first().url if l["product"].images.first() else ""),
                "quantity": l["quantity"],
                "unit_price_cents": l["unit_price_cents"],
                "extra_cents": l["extra_cents"],
                "line_total_cents": l["line_total_cents"],
                "options": l["options"],
                "product_type": l["product"].product_type,
            }
            for l in lines
        ],
        "totals": {
            "subtotal_cents": subtotal,
            "discount_cents": discount_cents,
            "shipping_cents": shipping["shipping_cents"] if shipping.get("available") else 0,
            "total_cents": total if shipping.get("available") is not False else after_discount,
            "currency": currency,
        },
        "shipping": shipping,
        "coupon_applied": coupon.code if coupon else None,
        "payment_methods": get_payment_methods(currency),
        "shipping_countries": [
            {"id": c.id, "country_name": c.country_name, "country_code": c.country_code}
            for c in list_enabled_countries()
        ],
    }


def checkout_store(items, customer, delivery, coupon_code, payment_method):
    customer = customer or {}
    delivery = delivery or {}
    name = (customer.get("full_name") or customer.get("name") or "").strip()
    email = (customer.get("email") or "").strip()
    phone = (customer.get("phone") or "").strip()
    if not name:
        raise ValueError("Full name is required.")
    if not _email_ok(email):
        raise ValueError("A valid email is required.")
    if not phone:
        raise ValueError("Phone number is required.")

    lines = _line_items_from_request(items)
    products = [l["product"] for l in lines]
    requires_shipping = any(
        (p.product_type or "physical") != "digital" and p.shipping_required for p in products
    )

    country = (delivery.get("country") or "").strip()
    region = (delivery.get("region") or delivery.get("state") or "").strip()
    city = (delivery.get("city") or "").strip()
    address = (delivery.get("address") or "").strip()
    postal = (delivery.get("postal") or delivery.get("zip") or "").strip()

    if requires_shipping:
        if not country:
            raise ValueError("Country is required for delivery.")
        if not city or not address:
            raise ValueError("City and address are required for delivery.")

    # Lock + reserve in a consistent id order to reduce deadlocks
    locked = {}
    for pid in sorted({l["product"].id for l in lines}):
        product = lock_store_product(pid)
        if not product or not product.is_public():
            raise ValueError("One of the products is not available.")
        locked[pid] = product

    reserved = []
    try:
        for line in lines:
            product = locked[line["product"].id]
            line["product"] = product
            try:
                reserve_stock(product, line["quantity"])
            except InventoryError as exc:
                raise ValueError(str(exc))
            reserved.append((product, line["quantity"]))

        subtotal = sum(l["line_total_cents"] for l in lines)
        discount_cents, coupon = validate_and_apply_coupon(
            coupon_code,
            subtotal,
            {"store": True, "store_product_ids": [p.id for p in products]},
        )
        after_discount = max(0, subtotal - discount_cents)

        if requires_shipping:
            ship = calculate_shipping(country, region, after_discount, [l["product"] for l in lines])
            shipping_cents = ship["shipping_cents"]
            ship_note = ship.get("note") or ""
        else:
            shipping_cents = 0
            ship_note = "Digital order — no shipping."

        total = after_discount + shipping_cents
        currency = lines[0]["currency"]
        provider = (payment_method or "manual").lower()
        if total <= 0:
            provider = "coupon"

        order = StoreOrder(
            order_number=generate_reference("BX"),
            customer_name=name[:255],
            customer_email=email[:255],
            customer_phone=phone[:64],
            ship_country=country[:120],
            ship_region=region[:160],
            ship_city=city[:160],
            ship_address=address,
            ship_postal=postal[:32],
            subtotal_cents=subtotal,
            discount_cents=discount_cents,
            shipping_cents=shipping_cents,
            total_cents=total,
            currency=currency,
            payment_method=provider,
            payment_status="pending",
            order_status="pending_payment",
            requires_shipping=requires_shipping,
            shipping_note=ship_note[:255],
            access_token=generate_token(18),
        )
        db.session.add(order)
        db.session.flush()

        for line in lines:
            p = line["product"]
            db.session.add(StoreOrderItem(
                order_id=order.id,
                product_id=p.id,
                product_title=p.title,
                product_slug=p.slug,
                sku=p.sku or "",
                quantity=line["quantity"],
                unit_price_cents=line["unit_price_cents"],
                extra_cents=line["extra_cents"],
                line_total_cents=line["line_total_cents"],
                options_json=json.dumps(line["options"] or {}),
                product_type=p.product_type or "physical",
            ))

        totals = {
            "subtotal_cents": subtotal,
            "discount_cents": discount_cents,
            "fee_cents": shipping_cents,
            "total_cents": total,
            "currency": currency,
            "coupon": coupon,
        }
        payment = _create_payment_record(
            "store_order",
            totals,
            None,
            None,
            provider=provider,
            customer_info={"full_name": name, "email": email, "phone": phone},
        )
        order.payment_id = payment.id
        db.session.flush()

        if total <= 0:
            fulfill_payment(payment)
            return payment, order

        title = lines[0]["product"].title if len(lines) == 1 else f"Store order {order.order_number}"
        payment = _init_provider_session(
            payment,
            title,
            {"payment_reference": payment.payment_reference, "store_order_id": order.id},
            return_path=f"store-checkout.html?payment_ref={payment.payment_reference}&status=return",
            cancel_path=f"store-checkout.html?payment_ref={payment.payment_reference}&status=cancel",
        )
        db.session.commit()
        return payment, order
    except Exception:
        db.session.rollback()
        raise


def store_order_for_payment(payment):
    if not payment:
        return None
    return StoreOrder.query.filter_by(payment_id=payment.id).first()


def public_order_lookup(order_number, access_token):
    order = StoreOrder.query.filter_by(order_number=order_number).first()
    if not order or order.access_token != access_token:
        raise ValueError("Order not found.")
    return order
