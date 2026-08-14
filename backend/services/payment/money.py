"""Money parsing and formatting helpers."""

import re

_PRICE_RE = re.compile(r"[^\d.]+")


def parse_price_to_cents(value, default=0):
    """Parse '$50', '50.00', or 50 into integer cents."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value * 100))
    text = str(value).strip()
    if not text:
        return default
    cleaned = _PRICE_RE.sub("", text)
    if not cleaned:
        return default
    try:
        return int(round(float(cleaned) * 100))
    except ValueError:
        return default


def cents_to_display(cents, currency="USD"):
    amount = (cents or 0) / 100.0
    if currency == "GMD":
        return f"{amount:,.0f} {currency}"
    return f"{amount:,.2f} {currency}"


def generate_reference(prefix):
    from models import generate_token

    return f"{prefix}-{generate_token()[:12].upper()}"
