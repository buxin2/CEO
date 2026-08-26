"""
Fixed FedEx zone shipping for a 0.6 kg parcel originating in India.

No shipping APIs. Prices are estimated FedEx International charges in USD cents.
Admin can override a zone's rate_cents in the database; country-to-zone maps stay here.
"""

from services.iso_countries import COUNTRIES, resolve_country
from services.payment.money import parse_price_to_cents

CARRIER = "FedEx"
UNAVAILABLE_MSG = "FedEx shipping is currently unavailable for this destination."

# zone_slug -> display name, default USD cents, ISO country codes
# Prices: estimated FedEx Intl for ~0.6 kg from India. Edit defaults here or in Admin → Shipping.
ZONES = {
    "domestic_india": {
        "name": "India (domestic)",
        "rate_cents": 1500,
        "countries": ["IN"],
    },
    "south_asia": {
        "name": "South Asia",
        "rate_cents": 2800,
        "countries": ["PK", "BD", "LK", "NP", "BT", "MV", "AF"],
    },
    "southeast_asia": {
        "name": "Southeast Asia",
        "rate_cents": 3200,
        "countries": ["TH", "VN", "MY", "SG", "ID", "PH", "MM", "KH", "LA", "BN", "TL"],
    },
    "east_asia": {
        "name": "East Asia",
        "rate_cents": 3600,
        "countries": ["JP", "KR", "CN", "HK", "TW", "MO", "MN", "KP"],
    },
    "central_asia": {
        "name": "Central Asia",
        "rate_cents": 4200,
        "countries": ["KZ", "UZ", "TM", "KG", "TJ"],
    },
    "middle_east": {
        "name": "Middle East",
        "rate_cents": 3800,
        "countries": ["AE", "SA", "QA", "KW", "BH", "OM", "JO", "LB", "IL", "IQ", "IR", "YE", "SY", "PS", "TR"],
    },
    "north_africa": {
        "name": "North Africa",
        "rate_cents": 4500,
        "countries": ["EG", "LY", "TN", "DZ", "MA", "SD", "EH"],
    },
    "west_africa": {
        "name": "West Africa",
        "rate_cents": 5200,
        "countries": ["GM", "SN", "GH", "NG", "BJ", "TG", "CI", "LR", "SL", "GN", "GW", "ML", "BF", "NE", "MR", "CV"],
    },
    "east_africa": {
        "name": "East Africa",
        "rate_cents": 5000,
        "countries": ["KE", "TZ", "UG", "RW", "BI", "ET", "SO", "DJ", "ER", "SS", "SC", "KM", "MG", "MU", "RE", "YT"],
    },
    "central_africa": {
        "name": "Central Africa",
        "rate_cents": 5800,
        "countries": ["CM", "CF", "TD", "CG", "CD", "GA", "GQ", "ST"],
    },
    "southern_africa": {
        "name": "Southern Africa",
        "rate_cents": 4800,
        "countries": ["ZA", "NA", "BW", "ZW", "ZM", "MW", "LS", "SZ", "MZ", "AO", "SH"],
    },
    "united_kingdom_ireland": {
        "name": "United Kingdom & Ireland",
        "rate_cents": 4000,
        "countries": ["GB", "IE", "IM", "JE", "GG"],
    },
    "western_europe": {
        "name": "Western Europe",
        "rate_cents": 4200,
        "countries": ["FR", "DE", "NL", "BE", "LU", "AT", "CH", "LI", "MC", "AD"],
    },
    "northern_europe": {
        "name": "Northern Europe",
        "rate_cents": 4600,
        "countries": ["NO", "SE", "DK", "FI", "IS", "AX", "FO", "GL", "SJ"],
    },
    "southern_europe": {
        "name": "Southern Europe",
        "rate_cents": 4400,
        "countries": ["ES", "PT", "IT", "GR", "MT", "CY", "SM", "VA", "GI"],
    },
    "eastern_europe": {
        "name": "Eastern Europe",
        "rate_cents": 4800,
        "countries": [
            "PL", "CZ", "SK", "HU", "RO", "BG", "HR", "SI", "RS", "BA", "ME", "MK",
            "AL", "XK", "MD", "UA", "BY", "RU", "EE", "LV", "LT", "GE", "AM", "AZ",
        ],
    },
    "north_america": {
        "name": "North America",
        "rate_cents": 5500,
        "countries": ["US", "CA", "UM", "PR", "GU", "AS", "MP", "VI", "PM"],
    },
    "central_america": {
        "name": "Central America",
        "rate_cents": 5800,
        "countries": ["MX", "GT", "BZ", "HN", "SV", "NI", "CR", "PA"],
    },
    "caribbean": {
        "name": "Caribbean",
        "rate_cents": 6200,
        "countries": [
            "BS", "BB", "JM", "HT", "DO", "CU", "TT", "AG", "DM", "GD", "KN", "LC",
            "VC", "KY", "BM", "AW", "CW", "SX", "BQ", "GP", "MQ", "BL", "MF", "TC",
            "VG", "AI", "MS",
        ],
    },
    "south_america": {
        "name": "South America",
        "rate_cents": 6500,
        "countries": ["AR", "BO", "BR", "CL", "CO", "EC", "FK", "GF", "GY", "PY", "PE", "SR", "UY", "VE", "GS"],
    },
    "oceania": {
        "name": "Oceania",
        "rate_cents": 4800,
        "countries": ["AU", "NZ", "CX", "CC", "NF", "HM"],
    },
    "pacific_islands": {
        "name": "Pacific Islands",
        "rate_cents": 7200,
        "countries": [
            "FJ", "PG", "SB", "VU", "NC", "PF", "WS", "TO", "KI", "MH", "FM", "PW",
            "NR", "TV", "NU", "CK", "TK", "WF", "PN",
        ],
    },
    "remote_territories": {
        "name": "Remote territories",
        "rate_cents": 8500,
        "countries": ["AQ", "BV", "IO", "TF"],
    },
}


def _country_to_zone():
    mapping = {}
    for slug, zone in ZONES.items():
        for code in zone["countries"]:
            if code in mapping:
                raise RuntimeError(f"Country {code} mapped to both {mapping[code]} and {slug}")
            mapping[code] = slug
    return mapping


COUNTRY_TO_ZONE = _country_to_zone()


def unmapped_iso_countries():
    known = {code for code, _name in COUNTRIES}
    mapped = set(COUNTRY_TO_ZONE)
    return sorted(known - mapped)


if unmapped_iso_countries():
    raise RuntimeError("Unmapped shipping countries: " + ", ".join(unmapped_iso_countries()))


def _overrides():
    from models import FedexZoneRate

    rows = FedexZoneRate.query.all()
    return {row.zone_slug: int(row.rate_cents or 0) for row in rows if row.zone_slug}


def zone_rate_cents(slug, overrides=None):
    zone = ZONES.get(slug)
    if not zone:
        return None
    if overrides is None:
        try:
            overrides = _overrides()
        except Exception:
            overrides = {}
    if slug in overrides and overrides[slug] > 0:
        return overrides[slug]
    return int(zone["rate_cents"])


def lookup_fedex(country_value):
    """Return zone quote for a country code or name. Never returns $0 for a mapped country."""
    code, name = resolve_country(country_value)
    if not code:
        return {
            "available": False,
            "error": UNAVAILABLE_MSG,
            "carrier": CARRIER,
            "shipping_cents": 0,
        }
    slug = COUNTRY_TO_ZONE.get(code)
    if not slug or slug not in ZONES:
        return {
            "available": False,
            "error": UNAVAILABLE_MSG,
            "carrier": CARRIER,
            "country_code": code,
            "country_name": name,
            "shipping_cents": 0,
        }
    cents = zone_rate_cents(slug)
    if not cents or cents <= 0:
        return {
            "available": False,
            "error": UNAVAILABLE_MSG,
            "carrier": CARRIER,
            "country_code": code,
            "country_name": name,
            "zone_slug": slug,
            "zone_name": ZONES[slug]["name"],
            "shipping_cents": 0,
        }
    return {
        "available": True,
        "carrier": CARRIER,
        "country_code": code,
        "country_name": name,
        "zone_slug": slug,
        "zone_name": ZONES[slug]["name"],
        "shipping_cents": cents,
        "currency": "USD",
    }


def zones_for_admin():
    from services.iso_countries import COUNTRIES as ISO

    names = {code: name for code, name in ISO}
    overrides = {}
    try:
        overrides = _overrides()
    except Exception:
        overrides = {}
    rows = []
    for slug, zone in ZONES.items():
        countries = [
            {"code": c, "name": names.get(c, c)}
            for c in zone["countries"]
        ]
        countries.sort(key=lambda r: r["name"].casefold())
        rows.append({
            "slug": slug,
            "name": zone["name"],
            "default_rate_cents": int(zone["rate_cents"]),
            "rate_cents": zone_rate_cents(slug, overrides),
            "carrier": CARRIER,
            "countries": countries,
        })
    return rows


def update_zone_rate(slug, rate):
    from models import FedexZoneRate, db

    if slug not in ZONES:
        raise ValueError("Unknown shipping zone.")
    cents = parse_price_to_cents(rate)
    if cents <= 0:
        raise ValueError("FedEx price must be greater than zero.")
    row = FedexZoneRate.query.filter_by(zone_slug=slug).first()
    if not row:
        row = FedexZoneRate(zone_slug=slug, rate_cents=cents)
        db.session.add(row)
    else:
        row.rate_cents = cents
    db.session.commit()
    return lookup_zone_admin(slug)


def lookup_zone_admin(slug):
    for row in zones_for_admin():
        if row["slug"] == slug:
            return row
    raise ValueError("Unknown shipping zone.")
