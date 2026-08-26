"""Admin store catalog: products, categories, related products, analytics."""

import re
from datetime import datetime

from models import (
    db,
    StoreCategory,
    StoreOrder,
    StoreOrderItem,
    StoreProduct,
    StoreProductImage,
    StoreProductOption,
    StoreProductOptionValue,
    StoreProductRelated,
    StoreProductVideo,
    StoreSettings,
    generate_token,
)
from services.store_media import parse_video_link, sanitize_html
from utils import store_link, store_product_link

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text):
    base = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")[:160] or "product"
    return base


def unique_slug(text, exclude_id=None, model=StoreProduct):
    base = slugify(text)
    slug = base
    n = 2
    while True:
        q = model.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{n}"
        n += 1


def get_or_create_settings():
    row = StoreSettings.query.first()
    if not row:
        row = StoreSettings(store_name="Store", tagline="Shop our products")
        db.session.add(row)
        db.session.commit()
    return row


def update_settings(data):
    row = get_or_create_settings()
    if data.get("store_name") is not None:
        row.store_name = str(data["store_name"]).strip()[:255] or "Store"
    if data.get("tagline") is not None:
        row.tagline = str(data["tagline"]).strip()[:500]
    if data.get("logo_url") is not None:
        row.logo_url = str(data["logo_url"]).strip()[:500]
    if data.get("currency") is not None:
        row.currency = str(data["currency"]).strip().upper()[:10] or "USD"
    if "free_shipping_min_cents" in data:
        val = data.get("free_shipping_min_cents")
        row.free_shipping_min_cents = int(val) if val not in (None, "") else None
    for field in (
        "origin_name", "origin_street", "origin_city", "origin_state", "origin_zip",
        "origin_phone", "origin_email", "customs_signer",
    ):
        if data.get(field) is not None:
            setattr(row, field, str(data.get(field) or "").strip()[:255])
    if data.get("origin_country") is not None:
        from services.iso_countries import resolve_country
        code, _name = resolve_country(data.get("origin_country"))
        row.origin_country = (code or "IN")[:8]
    for field, default in (
        ("default_weight_kg", 0.6),
        ("default_length_cm", 20.0),
        ("default_width_cm", 15.0),
        ("default_height_cm", 8.0),
    ):
        if data.get(field) is not None and data.get(field) != "":
            try:
                setattr(row, field, float(data[field]))
            except (TypeError, ValueError):
                setattr(row, field, default)
    db.session.commit()
    return row


def list_categories():
    return StoreCategory.query.order_by(StoreCategory.sort_order.asc(), StoreCategory.name.asc()).all()


def create_category(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Category name is required.")
    cat = StoreCategory(
        name=name[:120],
        slug=unique_slug(data.get("slug") or name, model=StoreCategory),
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(cat)
    db.session.commit()
    return cat


def update_category(category_id, data):
    cat = StoreCategory.query.get(category_id)
    if not cat:
        raise ValueError("Category not found.")
    if data.get("name"):
        cat.name = str(data["name"]).strip()[:120]
    if data.get("slug"):
        cat.slug = unique_slug(data["slug"], exclude_id=cat.id, model=StoreCategory)
    if data.get("sort_order") is not None:
        cat.sort_order = int(data["sort_order"])
    db.session.commit()
    return cat


def delete_category(category_id):
    cat = StoreCategory.query.get(category_id)
    if not cat:
        raise ValueError("Category not found.")
    StoreProduct.query.filter_by(category_id=cat.id).update({"category_id": None})
    db.session.delete(cat)
    db.session.commit()


def _apply_options(product, options):
    StoreProductOption.query.filter_by(product_id=product.id).delete()
    db.session.flush()
    for i, opt in enumerate(options or []):
        name = (opt.get("name") or "").strip()
        if not name:
            continue
        row = StoreProductOption(product_id=product.id, name=name[:80], sort_order=i)
        db.session.add(row)
        db.session.flush()
        for j, val in enumerate(opt.get("values") or []):
            if isinstance(val, str):
                label, extra = val, 0
            else:
                label = (val.get("label") or "").strip()
                extra = int(val.get("extra_cents") or 0)
            if not label:
                continue
            db.session.add(StoreProductOptionValue(
                option_id=row.id, label=label[:80], extra_cents=max(0, extra), sort_order=j
            ))


def _apply_related(product, related_ids):
    StoreProductRelated.query.filter_by(product_id=product.id).delete()
    seen = set()
    for rid in related_ids or []:
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            continue
        if rid == product.id or rid in seen:
            continue
        if not StoreProduct.query.get(rid):
            continue
        seen.add(rid)
        db.session.add(StoreProductRelated(product_id=product.id, related_product_id=rid))


def _apply_images(product, images, replace=True):
    if replace:
        StoreProductImage.query.filter_by(product_id=product.id).delete()
        db.session.flush()
    existing_count = StoreProductImage.query.filter_by(product_id=product.id).count()
    for i, img in enumerate(images or []):
        url = img if isinstance(img, str) else (img.get("url") or "")
        url = str(url).strip()
        if not url:
            continue
        alt = "" if isinstance(img, str) else (img.get("alt_text") or "")
        db.session.add(StoreProductImage(
            product_id=product.id,
            url=url[:500],
            alt_text=str(alt)[:255],
            sort_order=existing_count + i,
        ))


def _apply_videos(product, videos, replace=True):
    if replace:
        StoreProductVideo.query.filter_by(product_id=product.id).delete()
        db.session.flush()
    existing_count = StoreProductVideo.query.filter_by(product_id=product.id).count()
    for i, vid in enumerate(videos or []):
        url = vid if isinstance(vid, str) else (vid.get("url") or "")
        url = str(url).strip()
        if not url:
            continue
        parsed = parse_video_link(url)
        title = "" if isinstance(vid, str) else (vid.get("title") or "")
        vtype = parsed["video_type"]
        if not isinstance(vid, str) and vid.get("video_type"):
            vtype = vid["video_type"]
        db.session.add(StoreProductVideo(
            product_id=product.id,
            video_type=vtype[:20],
            url=parsed["url"][:500],
            embed_url=(parsed.get("embed_url") or parsed["url"])[:500],
            title=str(title)[:255],
            sort_order=existing_count + i,
        ))


def _product_fields(product, data, is_create=False):
    if data.get("title") or is_create:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("Product title is required.")
        product.title = title[:255]
    if data.get("slug") or (is_create and product.title):
        product.slug = unique_slug(data.get("slug") or product.title, exclude_id=product.id)
    if "short_description" in data:
        product.short_description = str(data.get("short_description") or "")[:500]
    if "description" in data:
        product.description = sanitize_html(data.get("description") or "")
    if "specifications" in data:
        product.specifications = sanitize_html(data.get("specifications") or "")
    if "sku" in data:
        product.sku = str(data.get("sku") or "")[:80]
    if "category_id" in data:
        product.category_id = data.get("category_id") or None
    if data.get("product_type"):
        ptype = str(data["product_type"]).strip().lower()
        product.product_type = ptype if ptype in ("physical", "digital") else "physical"
        product.shipping_required = product.product_type == "physical"
    if "shipping_required" in data:
        product.shipping_required = bool(data["shipping_required"]) and product.product_type != "digital"
    if "free_shipping" in data:
        product.free_shipping = bool(data["free_shipping"])
    for field in ("weight_kg", "length_cm", "width_cm", "height_cm"):
        if field in data:
            val = data.get(field)
            if val in (None, ""):
                setattr(product, field, None)
            else:
                try:
                    setattr(product, field, float(val))
                except (TypeError, ValueError):
                    pass
    if data.get("status"):
        status = str(data["status"]).strip().lower()
        if status in ("active", "draft", "out_of_stock", "hidden"):
            product.status = status
    if data.get("price") is not None or data.get("price_cents") is not None:
        from services.payment.money import parse_price_to_cents
        if data.get("price_cents") is not None:
            product.price_cents = max(0, int(data["price_cents"]))
        else:
            product.price_cents = max(0, parse_price_to_cents(data.get("price")))
    if "sale_price" in data or "sale_price_cents" in data:
        from services.payment.money import parse_price_to_cents
        if data.get("sale_price_cents") is not None:
            product.sale_price_cents = int(data["sale_price_cents"]) if data["sale_price_cents"] != "" else None
        elif data.get("sale_price") in (None, ""):
            product.sale_price_cents = None
        else:
            product.sale_price_cents = parse_price_to_cents(data.get("sale_price"))
    if data.get("currency"):
        product.currency = str(data["currency"]).strip().upper()[:10]
    if "quantity_available" in data:
        val = data.get("quantity_available")
        product.quantity_available = None if val in (None, "", "unlimited") else max(0, int(val))
    if "digital_delivery_url" in data:
        product.digital_delivery_url = str(data.get("digital_delivery_url") or "")[:500]
    if "digital_delivery_text" in data:
        product.digital_delivery_text = str(data.get("digital_delivery_text") or "")
    if "keywords" in data:
        product.keywords = str(data.get("keywords") or "")[:500]
    product.updated_at = datetime.utcnow()


def create_product(data):
    product = StoreProduct(
        title="Untitled",
        slug=unique_slug(data.get("slug") or data.get("title") or "product"),
        status="draft",
        currency=(data.get("currency") or get_or_create_settings().currency or "USD"),
        preview_token=generate_token(16),
    )
    _product_fields(product, data, is_create=True)
    if product.product_type != "digital" and product.quantity_available is None:
        product.quantity_available = 0
    db.session.add(product)
    db.session.flush()
    _apply_images(product, data.get("images") or [], replace=True)
    _apply_videos(product, data.get("videos") or [], replace=True)
    _apply_options(product, data.get("options") or [])
    _apply_related(product, data.get("related_ids") or data.get("related_product_ids") or [])
    db.session.commit()
    return product


def update_product(product_id, data):
    product = StoreProduct.query.get(product_id)
    if not product:
        raise ValueError("Product not found.")
    _product_fields(product, data)
    if "images" in data:
        _apply_images(product, data.get("images") or [], replace=True)
    if "videos" in data:
        _apply_videos(product, data.get("videos") or [], replace=True)
    if "options" in data:
        _apply_options(product, data.get("options") or [])
    if "related_ids" in data or "related_product_ids" in data:
        _apply_related(product, data.get("related_ids") or data.get("related_product_ids") or [])
    db.session.commit()
    return product


def delete_product(product_id):
    product = StoreProduct.query.get(product_id)
    if not product:
        raise ValueError("Product not found.")
    StoreProductRelated.query.filter(
        (StoreProductRelated.product_id == product.id) | (StoreProductRelated.related_product_id == product.id)
    ).delete(synchronize_session=False)
    db.session.delete(product)
    db.session.commit()


def add_image_url(product_id, url, alt_text=""):
    product = StoreProduct.query.get(product_id)
    if not product:
        raise ValueError("Product not found.")
    _apply_images(product, [{"url": url, "alt_text": alt_text}], replace=False)
    db.session.commit()
    return product


def add_video_url(product_id, url, title=""):
    product = StoreProduct.query.get(product_id)
    if not product:
        raise ValueError("Product not found.")
    _apply_videos(product, [{"url": url, "title": title}], replace=False)
    db.session.commit()
    return product


def delete_image(image_id):
    row = StoreProductImage.query.get(image_id)
    if not row:
        raise ValueError("Image not found.")
    db.session.delete(row)
    db.session.commit()


def delete_video(video_id):
    row = StoreProductVideo.query.get(video_id)
    if not row:
        raise ValueError("Video not found.")
    db.session.delete(row)
    db.session.commit()


def list_admin_products(search=None, status=None, category_id=None):
    q = StoreProduct.query
    if status:
        q = q.filter(StoreProduct.status == status)
    if category_id:
        q = q.filter(StoreProduct.category_id == category_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            db.or_(
                StoreProduct.title.ilike(like),
                StoreProduct.sku.ilike(like),
                StoreProduct.keywords.ilike(like),
                StoreProduct.short_description.ilike(like),
            )
        )
    return q.order_by(StoreProduct.updated_at.desc()).all()


def public_query(search=None, category=None):
    q = StoreProduct.query.filter(StoreProduct.status == "active")
    if category:
        cat = StoreCategory.query.filter(
            db.or_(StoreCategory.slug == category, StoreCategory.name.ilike(category))
        ).first()
        if cat:
            q = q.filter(StoreProduct.category_id == cat.id)
        else:
            q = q.filter(StoreProduct.id == -1)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            db.or_(
                StoreProduct.title.ilike(like),
                StoreProduct.keywords.ilike(like),
                StoreProduct.short_description.ilike(like),
                StoreProduct.description.ilike(like),
                StoreProduct.sku.ilike(like),
            )
        )
    return q.order_by(StoreProduct.created_at.desc())


def related_products(product, limit=6):
    manual_ids = [
        r.related_product_id
        for r in StoreProductRelated.query.filter_by(product_id=product.id).all()
    ]
    rows = []
    if manual_ids:
        rows = StoreProduct.query.filter(
            StoreProduct.id.in_(manual_ids),
            StoreProduct.status == "active",
        ).all()
    if len(rows) < limit and product.category_id:
        extra = (
            StoreProduct.query.filter(
                StoreProduct.category_id == product.category_id,
                StoreProduct.id != product.id,
                StoreProduct.status == "active",
            )
            .order_by(StoreProduct.view_count.desc())
            .limit(limit)
            .all()
        )
        have = {p.id for p in rows}
        for p in extra:
            if p.id not in have:
                rows.append(p)
            if len(rows) >= limit:
                break
    return [p.to_public_dict(include_media=True) for p in rows[:limit]]


def get_public_product(slug, preview_token=None):
    product = StoreProduct.query.filter_by(slug=slug).first()
    if not product:
        raise ValueError("Product not found.")
    if product.is_public():
        if not preview_token:
            product.view_count = (product.view_count or 0) + 1
            db.session.commit()
        return product
    if preview_token and product.preview_token and preview_token == product.preview_token:
        return product
    raise ValueError("This product is not available.")


def product_public_payload(product):
    return product.to_public_dict(related=related_products(product))


def admin_links(product):
    return {
        "store_url": store_link(),
        "product_url": store_product_link(product.slug),
        "preview_url": store_product_link(product.slug) + f"&preview={product.preview_token}",
    }


def analytics_for_product(product):
    items = StoreOrderItem.query.filter_by(product_id=product.id).all()
    order_ids = {i.order_id for i in items}
    orders = StoreOrder.query.filter(StoreOrder.id.in_(order_ids)).all() if order_ids else []
    paid = [o for o in orders if o.payment_status in ("succeeded", "paid") or o.order_status in ("paid", "processing", "packed", "shipped", "delivered")]
    pending = [o for o in orders if o.order_status == "pending_payment"]
    units = 0
    revenue = 0
    paid_ids = {o.id for o in paid}
    for item in items:
        if item.order_id in paid_ids:
            units += item.quantity or 0
            revenue += item.line_total_cents or 0
    return {
        "views": product.view_count or 0,
        "total_orders": len(paid),
        "pending_orders": len(pending),
        "units_sold": units,
        "units_remaining": product.sellable_quantity(),
        "revenue_cents": revenue,
    }


def overall_analytics():
    products = StoreProduct.query.all()
    orders = StoreOrder.query.all()
    paid = [o for o in orders if o.payment_status in ("succeeded", "paid") or o.order_status in ("paid", "processing", "packed", "shipped", "delivered")]
    return {
        "total_products": len(products),
        "active_products": sum(1 for p in products if p.status == "active"),
        "total_orders": len(orders),
        "total_sales": len(paid),
        "total_revenue_cents": sum(o.total_cents or 0 for o in paid),
        "pending_orders": sum(1 for o in orders if o.order_status == "pending_payment"),
    }


def find_product_by_name(name):
    name = (name or "").strip()
    if not name:
        return None
    exact = StoreProduct.query.filter(StoreProduct.title.ilike(name)).all()
    if len(exact) == 1:
        return exact[0]
    partial = StoreProduct.query.filter(StoreProduct.title.ilike(f"%{name}%")).all()
    if len(partial) == 1:
        return partial[0]
    return None
