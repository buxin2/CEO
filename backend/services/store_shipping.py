"""Server-side shipping calculation. Never trust frontend shipping amounts."""

from models import db, ShippingCountry, ShippingRegion, StoreSettings


class ShippingUnavailable(ValueError):
    pass


def _norm(value):
    return " ".join((value or "").strip().lower().split())


def find_country(country_name):
    name = (country_name or "").strip()
    if not name:
        return None
    exact = ShippingCountry.query.filter(ShippingCountry.country_name.ilike(name)).first()
    if exact:
        return exact
    code = name.upper()
    by_code = ShippingCountry.query.filter(ShippingCountry.country_code.ilike(code)).first()
    if by_code:
        return by_code
    return ShippingCountry.query.filter(ShippingCountry.country_name.ilike(f"%{name}%")).first()


def find_region(country, region_name):
    if not country or not (region_name or "").strip():
        return None
    wanted = _norm(region_name)
    for row in country.regions.all():
        if _norm(row.region_name) == wanted:
            return row
    for row in country.regions.all():
        if wanted in _norm(row.region_name) or _norm(row.region_name) in wanted:
            return row
    return None


def calculate_shipping(country_name, region_name, subtotal_cents, products):
    """
    Return shipping_cents for a destination.
    products: list of StoreProduct
    """
    products = products or []
    requires = any((p.product_type or "physical") != "digital" and p.shipping_required for p in products)
    if not requires:
        return {
            "shipping_cents": 0,
            "requires_shipping": False,
            "country": None,
            "region": None,
            "free_shipping": True,
            "note": "Digital order — no shipping.",
        }

    country = find_country(country_name)
    if not country or not country.is_enabled:
        raise ShippingUnavailable("Delivery is currently unavailable to this location.")

    region = find_region(country, region_name)
    rate = region.rate_cents if region is not None else (country.rate_cents or 0)

    all_products_free = bool(products) and all(bool(p.free_shipping) for p in products)
    settings = StoreSettings.query.first()
    global_min = settings.free_shipping_min_cents if settings else None

    free = False
    note = ""
    if all_products_free:
        free = True
        note = "Free shipping on selected products."
    elif country.free_shipping:
        min_cents = country.free_shipping_min_cents
        if min_cents is None or (subtotal_cents or 0) >= min_cents:
            free = True
            note = "Free shipping to this country."
    elif global_min is not None and (subtotal_cents or 0) >= global_min:
        free = True
        note = "Free shipping on this order."
    elif country.free_shipping_min_cents is not None and (subtotal_cents or 0) >= country.free_shipping_min_cents:
        free = True
        note = "Free shipping above the country minimum."

    return {
        "shipping_cents": 0 if free else int(rate or 0),
        "requires_shipping": True,
        "country": country,
        "region": region,
        "free_shipping": free,
        "note": note or (f"Regional rate for {region.region_name}." if region else f"Country rate for {country.country_name}."),
    }


def list_enabled_countries():
    return ShippingCountry.query.filter_by(is_enabled=True).order_by(ShippingCountry.country_name.asc()).all()


def list_all_countries():
    return ShippingCountry.query.order_by(ShippingCountry.country_name.asc()).all()


def create_country(data):
    name = (data.get("country_name") or data.get("name") or "").strip()
    if not name:
        raise ValueError("Country name is required.")
    from services.payment.money import parse_price_to_cents

    row = ShippingCountry(
        country_name=name[:120],
        country_code=(data.get("country_code") or "")[:8].upper(),
        rate_cents=int(data["rate_cents"]) if data.get("rate_cents") is not None else parse_price_to_cents(data.get("rate") or data.get("shipping_rate") or 0),
        currency=(data.get("currency") or "USD")[:10].upper(),
        is_enabled=bool(data.get("is_enabled", True)),
        free_shipping=bool(data.get("free_shipping", False)),
        free_shipping_min_cents=(
            int(data["free_shipping_min_cents"])
            if data.get("free_shipping_min_cents") not in (None, "")
            else (parse_price_to_cents(data["free_shipping_min"]) if data.get("free_shipping_min") else None)
        ),
    )
    db.session.add(row)
    db.session.commit()
    return row


def update_country(country_id, data):
    from services.payment.money import parse_price_to_cents
    from models import db

    row = ShippingCountry.query.get(country_id)
    if not row:
        raise ValueError("Country not found.")
    if data.get("country_name") or data.get("name"):
        row.country_name = str(data.get("country_name") or data.get("name")).strip()[:120]
    if "country_code" in data:
        row.country_code = str(data.get("country_code") or "")[:8].upper()
    if data.get("rate_cents") is not None:
        row.rate_cents = int(data["rate_cents"])
    elif data.get("rate") is not None or data.get("shipping_rate") is not None:
        row.rate_cents = parse_price_to_cents(data.get("rate") or data.get("shipping_rate"))
    if data.get("currency"):
        row.currency = str(data["currency"]).strip().upper()[:10]
    if "is_enabled" in data:
        row.is_enabled = bool(data["is_enabled"])
    if "free_shipping" in data:
        row.free_shipping = bool(data["free_shipping"])
    if "free_shipping_min_cents" in data:
        val = data.get("free_shipping_min_cents")
        row.free_shipping_min_cents = int(val) if val not in (None, "") else None
    db.session.commit()
    return row


def delete_country(country_id):
    from models import db

    row = ShippingCountry.query.get(country_id)
    if not row:
        raise ValueError("Country not found.")
    db.session.delete(row)
    db.session.commit()


def add_region(country_id, data):
    from services.payment.money import parse_price_to_cents
    from models import db

    country = ShippingCountry.query.get(country_id)
    if not country:
        raise ValueError("Country not found.")
    name = (data.get("region_name") or data.get("name") or "").strip()
    if not name:
        raise ValueError("Region name is required.")
    row = ShippingRegion(
        country_id=country.id,
        region_name=name[:160],
        rate_cents=int(data["rate_cents"]) if data.get("rate_cents") is not None else parse_price_to_cents(data.get("rate") or 0),
    )
    db.session.add(row)
    db.session.commit()
    return row


def update_region(region_id, data):
    from services.payment.money import parse_price_to_cents
    from models import db

    row = ShippingRegion.query.get(region_id)
    if not row:
        raise ValueError("Region not found.")
    if data.get("region_name") or data.get("name"):
        row.region_name = str(data.get("region_name") or data.get("name")).strip()[:160]
    if data.get("rate_cents") is not None:
        row.rate_cents = int(data["rate_cents"])
    elif data.get("rate") is not None:
        row.rate_cents = parse_price_to_cents(data.get("rate"))
    db.session.commit()
    return row


def delete_region(region_id):
    from models import db

    row = ShippingRegion.query.get(region_id)
    if not row:
        raise ValueError("Region not found.")
    db.session.delete(row)
    db.session.commit()

