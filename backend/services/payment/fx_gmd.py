"""USD (and other) amounts → whole Gambian dalasi for Modem Pay."""

import logging
import time
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

FALLBACK_USD_TO_GMD = 74.5
_CACHE_TTL = 3600
_cache = {"rates": None, "source": "fallback", "at": 0}


def _whole_dalasi(value):
    """Round half up to a whole dalasi (no floats sent to Modem Pay)."""
    n = int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(1, n)


def _configured_usd_to_gmd():
    try:
        from flask import current_app, has_app_context

        if not has_app_context():
            return None
        raw = current_app.config.get("MODEMPAY_USD_TO_GMD")
        if raw in (None, ""):
            return None
        rate = float(raw)
        if rate > 0:
            return rate
    except Exception:
        return None
    return None


def _fetch_usd_rates():
    import requests

    resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
    resp.raise_for_status()
    body = resp.json() or {}
    rates = body.get("rates") or {}
    gmd = float(rates.get("GMD") or 0)
    if gmd <= 0:
        raise ValueError("FX feed did not include GMD.")
    return {str(k).upper(): float(v) for k, v in rates.items() if v}


def usd_rates():
    configured = _configured_usd_to_gmd()
    now = time.time()
    if _cache["rates"] and now - _cache["at"] < _CACHE_TTL:
        rates = dict(_cache["rates"])
        if configured:
            rates["GMD"] = configured
            return rates, "config"
        return rates, _cache["source"]

    try:
        rates = _fetch_usd_rates()
        _cache["rates"] = rates
        _cache["source"] = "live"
        _cache["at"] = now
        if configured:
            rates = dict(rates)
            rates["GMD"] = configured
            return rates, "config"
        return rates, "live"
    except Exception as exc:
        logger.warning("USD/GMD live rate failed: %s", exc)
        rates = {"GMD": configured or FALLBACK_USD_TO_GMD, "USD": 1.0}
        if configured:
            return rates, "config"
        return rates, "fallback"


def quote_gmd(amount_cents, currency="USD", usd_to_gmd=None):
    """Convert store cents into an integer GMD amount (no decimals)."""
    cents = max(0, int(amount_cents or 0))
    cur = (currency or "USD").upper()
    major = cents / 100.0

    if cur == "GMD":
        amount = _whole_dalasi(major) if cents else 0
        return {
            "amount": amount,
            "currency": "GMD",
            "rate": 1.0,
            "source": "gmd",
            "original_cents": cents,
            "original_currency": "GMD",
        }

    source = "override"
    rates = {"GMD": float(usd_to_gmd), "USD": 1.0} if usd_to_gmd else None
    if rates is None:
        rates, source = usd_rates()
        if usd_to_gmd:
            rates["GMD"] = float(usd_to_gmd)
            source = "override"

    gmd_per_usd = float(rates.get("GMD") or FALLBACK_USD_TO_GMD)
    if gmd_per_usd <= 0:
        gmd_per_usd = FALLBACK_USD_TO_GMD
        source = "fallback"

    if cur == "USD":
        usd = major
    else:
        units_per_usd = float(rates.get(cur) or 0)
        if units_per_usd <= 0:
            raise ValueError(f"Cannot convert {cur} to Gambian dalasi for Modem Pay.")
        usd = major / units_per_usd

    amount = _whole_dalasi(usd * gmd_per_usd) if cents else 0
    return {
        "amount": int(amount),
        "currency": "GMD",
        "rate": gmd_per_usd,
        "source": source,
        "original_cents": cents,
        "original_currency": cur,
    }
