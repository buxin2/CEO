"""Public storefront and admin product/shipping/order APIs."""

from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from models import STORE_ORDER_STATUSES, StoreOrder, StoreProduct, db
from routes.auth import login_required
from services.iso_countries import country_options
from services.fedex_zones import update_zone_rate, zones_for_admin
from services.payment.checkout_service import (
    manual_payment_instructions,
    payment_by_reference,
    verify_and_capture_payment,
)
from services.store_checkout import (
    checkout_store,
    preview_store_checkout,
    public_order_lookup,
    store_order_for_payment,
)
from services.store_customer_service import (
    create_help_request,
    current_store_customer,
    list_customer_orders,
    list_help_requests,
    login_with_email,
    login_with_phone,
    logout_store_customer,
    mark_help_request,
    register_store_customer,
)
from services.store_service import (
    add_image_url,
    add_video_url,
    admin_links,
    analytics_for_product,
    create_category,
    create_product,
    delete_category,
    delete_image,
    delete_product,
    delete_video,
    get_or_create_settings,
    get_public_product,
    list_admin_products,
    list_categories,
    overall_analytics,
    product_public_payload,
    public_query,
    update_category,
    update_product,
    update_settings,
)
from services.store_shipping import (
    add_region,
    create_country,
    delete_country,
    delete_region,
    update_country,
    update_region,
)
from utils import store_link, store_order_link, store_product_link

store_bp = Blueprint("store", __name__)


def _store_payment_payload(payment, order=None):
    order = order or store_order_for_payment(payment)
    data = {
        "payment": payment.to_dict(include_private=True),
        "manual_instructions": manual_payment_instructions() if payment.provider == "manual" else None,
    }
    if order:
        data["order"] = order.to_dict(include_private=True)
        data["order_url"] = store_order_link(order.order_number, order.access_token)
    return data


# ---------- Public ----------


@store_bp.route("/api/store/countries", methods=["GET"])
def api_store_countries():
    return jsonify({"countries": country_options()})


@store_bp.route("/api/store", methods=["GET"])
def api_public_store():
    settings = get_or_create_settings()
    search = request.args.get("search") or request.args.get("q")
    category = request.args.get("category")
    products = public_query(search=search, category=category).all()
    visible = [p for p in products if p.is_public()]
    return jsonify({
        "store": settings.to_dict(),
        "store_url": store_link(),
        "categories": [c.to_dict() for c in list_categories()],
        "products": [p.to_public_dict(include_media=True) for p in visible],
        "destination_countries": country_options(),
    })


@store_bp.route("/api/store/products/<slug>", methods=["GET"])
def api_public_product(slug):
    preview = request.args.get("preview")
    try:
        product = get_public_product(slug, preview_token=preview)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    settings = get_or_create_settings()
    payload = product_public_payload(product)
    payload["store"] = settings.to_dict()
    payload["product_url"] = store_product_link(product.slug)
    payload["store_url"] = store_link()
    return jsonify(payload)


@store_bp.route("/api/store/checkout/preview", methods=["POST"])
def api_store_preview():
    data = request.get_json(silent=True) or {}
    try:
        preview = preview_store_checkout(
            data.get("items") or [],
            coupon_code=data.get("coupon_code"),
            country=(data.get("country") or (data.get("delivery") or {}).get("country")),
        )
        preview["store"] = get_or_create_settings().to_dict()
        preview["destination_countries"] = country_options()
        return jsonify(preview)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/auth/register", methods=["POST"])
def api_store_register():
    data = request.get_json(silent=True) or {}
    try:
        customer = register_store_customer(data)
        return jsonify({"customer": customer.to_dict()}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/auth/login", methods=["POST"])
def api_store_login():
    data = request.get_json(silent=True) or {}
    try:
        if (data.get("phone") or "").strip() and not (data.get("email") or "").strip():
            customer = login_with_phone(data.get("phone"), data.get("password"))
        else:
            customer = login_with_email(data.get("email"), data.get("password"))
        return jsonify({"customer": customer.to_dict()})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401


@store_bp.route("/api/store/auth/logout", methods=["POST"])
def api_store_logout():
    logout_store_customer()
    return jsonify({"success": True})


@store_bp.route("/api/store/auth/me", methods=["GET"])
def api_store_me():
    customer = current_store_customer()
    if not customer:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "customer": customer.to_dict()})


@store_bp.route("/api/store/auth/help", methods=["POST"])
def api_store_help():
    data = request.get_json(silent=True) or {}
    try:
        row = create_help_request(data)
        return jsonify({"success": True, "request": row.to_dict()}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/account/orders", methods=["GET"])
def api_store_my_orders():
    customer = current_store_customer()
    if not customer:
        return jsonify({"error": "Sign in to see your orders."}), 401
    orders = list_customer_orders(customer)
    return jsonify({"orders": [o.to_dict(include_private=True) for o in orders]})


@store_bp.route("/api/admin/store/account-help", methods=["GET"])
@login_required
def api_admin_store_help():
    return jsonify({"requests": [r.to_dict() for r in list_help_requests()]})


@store_bp.route("/api/admin/store/account-help/<int:request_id>", methods=["PUT"])
@login_required
def api_admin_store_help_update(request_id):
    data = request.get_json(silent=True) or {}
    try:
        row = mark_help_request(request_id, data.get("status") or "done")
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/checkout", methods=["POST"])
def api_store_checkout():
    customer = current_store_customer()
    if not customer:
        return jsonify({"error": "Sign in to buy. Create an account or log in first."}), 401
    data = request.get_json(silent=True) or {}
    guest = data.get("customer") or {}
    merged = {
        "full_name": (guest.get("full_name") or customer.full_name or "").strip() or customer.full_name,
        "email": customer.email,
        "phone": customer.phone,
    }
    try:
        payment, order = checkout_store(
            data.get("items") or [],
            merged,
            data.get("delivery") or {},
            data.get("coupon_code"),
            data.get("payment_method"),
            store_customer=customer,
            wallet_network=data.get("wallet_network"),
        )
        return jsonify(_store_payment_payload(payment, order)), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/checkout/verify/<payment_ref>", methods=["POST"])
def api_store_verify(payment_ref):
    data = request.get_json(silent=True) or {}
    try:
        payment = verify_and_capture_payment(payment_ref, paypal_order_id=data.get("paypal_order_id"))
        order = store_order_for_payment(payment)
        return jsonify(_store_payment_payload(payment, order))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/store/checkout/payment/<payment_ref>", methods=["GET"])
def api_store_payment(payment_ref):
    payment = payment_by_reference(payment_ref)
    if not payment or payment.payment_kind != "store_order":
        return jsonify({"error": "Payment not found."}), 404
    return jsonify(_store_payment_payload(payment))


@store_bp.route("/api/store/checkout/receipt/<payment_ref>", methods=["POST"])
def api_store_receipt(payment_ref):
    payment = payment_by_reference(payment_ref)
    if not payment or payment.payment_kind != "store_order":
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
    order = store_order_for_payment(payment)
    if order:
        order.payment_status = "manual_pending"
    db.session.commit()
    return jsonify(_store_payment_payload(payment))


@store_bp.route("/api/store/orders/<order_number>", methods=["GET"])
def api_public_order(order_number):
    token = request.args.get("token") or request.args.get("access_token")
    try:
        order = public_order_lookup(order_number, token)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    data = order.to_dict(include_private=True)
    data["store"] = get_or_create_settings().to_dict()
    return jsonify(data)


@store_bp.route("/p/<slug>", methods=["GET"])
def share_product_page(slug):
    """HTML page with Open Graph tags for social sharing."""
    from html import escape

    try:
        product = get_public_product(slug)
    except ValueError:
        return jsonify({"error": "Product not found."}), 404
    url = store_product_link(product.slug)
    cover = ""
    img = product.images.first()
    if img:
        cover = img.url
    title = escape(product.title)
    desc = escape((product.short_description or product.title)[:200])
    price = f"{(product.unit_price_cents() or 0) / 100:.2f} {escape(product.currency or 'USD')}"
    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="product">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc} — {price}">
<meta property="og:url" content="{escape(url)}">
{f'<meta property="og:image" content="{escape(cover)}">' if cover else ''}
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0;url={escape(url)}">
</head><body>
<p>Opening <a href="{escape(url)}">{title}</a>…</p>
</body></html>"""
    return Response(html, mimetype="text/html")


# ---------- Admin products ----------


@store_bp.route("/api/admin/store/settings", methods=["GET"])
@login_required
def api_admin_settings_get():
    s = get_or_create_settings()
    return jsonify({**s.to_dict(), "store_url": store_link()})


@store_bp.route("/api/admin/store/settings", methods=["PUT"])
@login_required
def api_admin_settings_put():
    s = update_settings(request.get_json(silent=True) or {})
    return jsonify({**s.to_dict(), "store_url": store_link()})


@store_bp.route("/api/admin/store/analytics", methods=["GET"])
@login_required
def api_admin_store_analytics():
    return jsonify(overall_analytics())


@store_bp.route("/api/admin/store/categories", methods=["GET"])
@login_required
def api_admin_categories():
    return jsonify({"categories": [c.to_dict() for c in list_categories()]})


@store_bp.route("/api/admin/store/categories", methods=["POST"])
@login_required
def api_admin_categories_create():
    try:
        cat = create_category(request.get_json(silent=True) or {})
        return jsonify(cat.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/categories/<int:category_id>", methods=["PUT"])
@login_required
def api_admin_categories_update(category_id):
    try:
        cat = update_category(category_id, request.get_json(silent=True) or {})
        return jsonify(cat.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/categories/<int:category_id>", methods=["DELETE"])
@login_required
def api_admin_categories_delete(category_id):
    try:
        delete_category(category_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/products", methods=["GET"])
@login_required
def api_admin_products():
    rows = list_admin_products(
        search=request.args.get("search"),
        status=request.args.get("status"),
        category_id=request.args.get("category_id", type=int),
    )
    out = []
    for p in rows:
        data = p.to_admin_dict()
        data.update(admin_links(p))
        data["analytics"] = analytics_for_product(p)
        out.append(data)
    return jsonify({"products": out, "analytics": overall_analytics(), "store_url": store_link()})


@store_bp.route("/api/admin/store/products", methods=["POST"])
@login_required
def api_admin_products_create():
    try:
        product = create_product(request.get_json(silent=True) or {})
        data = product.to_admin_dict()
        data.update(admin_links(product))
        return jsonify(data), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/products/<int:product_id>", methods=["GET"])
@login_required
def api_admin_product_get(product_id):
    product = StoreProduct.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    data = product.to_admin_dict()
    data.update(admin_links(product))
    data["analytics"] = analytics_for_product(product)
    return jsonify(data)


@store_bp.route("/api/admin/store/products/<int:product_id>", methods=["PUT"])
@login_required
def api_admin_product_update(product_id):
    try:
        product = update_product(product_id, request.get_json(silent=True) or {})
        data = product.to_admin_dict()
        data.update(admin_links(product))
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/products/<int:product_id>", methods=["DELETE"])
@login_required
def api_admin_product_delete(product_id):
    try:
        delete_product(product_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/products/<int:product_id>/images", methods=["POST"])
@login_required
def api_admin_product_image(product_id):
    product = StoreProduct.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    url = (request.form.get("url") or "").strip()
    if request.files.get("file") or request.files.get("image"):
        from services.store_media import upload_store_image

        try:
            result = upload_store_image(request.files.get("file") or request.files.get("image"), product_id)
            url = result.get("url") or url
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400
    if not url:
        return jsonify({"error": "Image file or URL is required."}), 400
    try:
        product = add_image_url(product_id, url, request.form.get("alt_text") or "")
        data = product.to_admin_dict()
        data.update(admin_links(product))
        return jsonify(data), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/products/<int:product_id>/videos", methods=["POST"])
@login_required
def api_admin_product_video(product_id):
    product = StoreProduct.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    url = (request.form.get("url") or "").strip()
    if request.files.get("file") or request.files.get("video"):
        from services.store_media import upload_store_video

        try:
            result = upload_store_video(request.files.get("file") or request.files.get("video"), product_id)
            url = result.get("url") or url
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400
    if not url:
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Video file or URL is required."}), 400
    try:
        title = request.form.get("title") or (request.get_json(silent=True) or {}).get("title") or ""
        product = add_video_url(product_id, url, title)
        data = product.to_admin_dict()
        data.update(admin_links(product))
        return jsonify(data), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/images/<int:image_id>", methods=["DELETE"])
@login_required
def api_admin_delete_image(image_id):
    try:
        delete_image(image_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/store/videos/<int:video_id>", methods=["DELETE"])
@login_required
def api_admin_delete_video(video_id):
    try:
        delete_video(video_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


# ---------- Shipping ----------


@store_bp.route("/api/admin/shipping", methods=["GET"])
@login_required
def api_admin_shipping():
    return jsonify({
        "carrier": "FedEx",
        "zones": zones_for_admin(),
    })


@store_bp.route("/api/admin/shipping/zones/<slug>", methods=["PUT"])
@login_required
def api_admin_shipping_zone(slug):
    data = request.get_json(silent=True) or {}
    try:
        row = update_zone_rate(slug, data.get("rate") if data.get("rate") is not None else data.get("rate_cents"))
        return jsonify(row)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/countries", methods=["POST"])
@login_required
def api_admin_shipping_create():
    try:
        row = create_country(request.get_json(silent=True) or {})
        return jsonify(row.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/countries/<int:country_id>", methods=["PUT"])
@login_required
def api_admin_shipping_update(country_id):
    try:
        row = update_country(country_id, request.get_json(silent=True) or {})
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/countries/<int:country_id>", methods=["DELETE"])
@login_required
def api_admin_shipping_delete(country_id):
    try:
        delete_country(country_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/countries/<int:country_id>/regions", methods=["POST"])
@login_required
def api_admin_region_create(country_id):
    try:
        row = add_region(country_id, request.get_json(silent=True) or {})
        return jsonify(row.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/regions/<int:region_id>", methods=["PUT"])
@login_required
def api_admin_region_update(region_id):
    try:
        row = update_region(region_id, request.get_json(silent=True) or {})
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@store_bp.route("/api/admin/shipping/regions/<int:region_id>", methods=["DELETE"])
@login_required
def api_admin_region_delete(region_id):
    try:
        delete_region(region_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


# ---------- Store orders ----------


@store_bp.route("/api/admin/store/orders", methods=["GET"])
@login_required
def api_admin_store_orders():
    q = StoreOrder.query.order_by(StoreOrder.created_at.desc())
    status = request.args.get("status")
    if status:
        q = q.filter(StoreOrder.order_status == status)
    rows = q.limit(500).all()
    return jsonify({"orders": [o.to_dict(include_private=True) for o in rows]})


@store_bp.route("/api/admin/store/orders/<int:order_id>", methods=["PUT"])
@login_required
def api_admin_store_order_update(order_id):
    order = StoreOrder.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    data = request.get_json(silent=True) or {}
    status = (data.get("order_status") or "").strip()
    if status:
        if status not in STORE_ORDER_STATUSES:
            return jsonify({"error": "Invalid order status."}), 400
        order.order_status = status
    for field in ("courier", "tracking_number", "tracking_url"):
        if data.get(field) is not None:
            setattr(order, field, str(data[field]).strip()[:500 if field == "tracking_url" else 120])
    order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(order.to_dict(include_private=True))


@store_bp.route("/api/admin/store/orders/<int:order_id>", methods=["GET"])
@login_required
def api_admin_store_order_get(order_id):
    order = StoreOrder.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    return jsonify(order.to_dict(include_private=True))
