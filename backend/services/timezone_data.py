"""Country / city options for user-local time (IANA timezone IDs)."""

# Curated list — city label shown in UI; multiple cities may share one timezone.
TIMEZONE_COUNTRIES = [
    {
        "name": "India",
        "cities": [
            {"name": "Mumbai", "timezone_id": "Asia/Kolkata", "label": "Mumbai (IST)"},
            {"name": "Delhi", "timezone_id": "Asia/Kolkata", "label": "Delhi (IST)"},
            {"name": "Kolkata", "timezone_id": "Asia/Kolkata", "label": "Kolkata (IST)"},
            {"name": "Chennai", "timezone_id": "Asia/Kolkata", "label": "Chennai (IST)"},
            {"name": "Bangalore", "timezone_id": "Asia/Kolkata", "label": "Bangalore (IST)"},
            {"name": "Hyderabad", "timezone_id": "Asia/Kolkata", "label": "Hyderabad (IST)"},
            {"name": "Ahmedabad", "timezone_id": "Asia/Kolkata", "label": "Ahmedabad (IST)"},
            {"name": "Pune", "timezone_id": "Asia/Kolkata", "label": "Pune (IST)"},
        ],
    },
    {
        "name": "United States",
        "cities": [
            {"name": "New York", "timezone_id": "America/New_York", "label": "New York (ET)"},
            {"name": "Chicago", "timezone_id": "America/Chicago", "label": "Chicago (CT)"},
            {"name": "Denver", "timezone_id": "America/Denver", "label": "Denver (MT)"},
            {"name": "Los Angeles", "timezone_id": "America/Los_Angeles", "label": "Los Angeles (PT)"},
            {"name": "Phoenix", "timezone_id": "America/Phoenix", "label": "Phoenix (AZ)"},
        ],
    },
    {
        "name": "United Kingdom",
        "cities": [
            {"name": "London", "timezone_id": "Europe/London", "label": "London (GMT/BST)"},
        ],
    },
    {
        "name": "France",
        "cities": [
            {"name": "Paris", "timezone_id": "Europe/Paris", "label": "Paris (CET)"},
        ],
    },
    {
        "name": "Germany",
        "cities": [
            {"name": "Berlin", "timezone_id": "Europe/Berlin", "label": "Berlin (CET)"},
        ],
    },
    {
        "name": "United Arab Emirates",
        "cities": [
            {"name": "Dubai", "timezone_id": "Asia/Dubai", "label": "Dubai (GST)"},
        ],
    },
    {
        "name": "China",
        "cities": [
            {"name": "Beijing", "timezone_id": "Asia/Shanghai", "label": "Beijing (CST)"},
            {"name": "Shanghai", "timezone_id": "Asia/Shanghai", "label": "Shanghai (CST)"},
        ],
    },
    {
        "name": "Japan",
        "cities": [
            {"name": "Tokyo", "timezone_id": "Asia/Tokyo", "label": "Tokyo (JST)"},
        ],
    },
    {
        "name": "Australia",
        "cities": [
            {"name": "Sydney", "timezone_id": "Australia/Sydney", "label": "Sydney (AEST)"},
            {"name": "Melbourne", "timezone_id": "Australia/Melbourne", "label": "Melbourne (AEST)"},
            {"name": "Perth", "timezone_id": "Australia/Perth", "label": "Perth (AWST)"},
        ],
    },
    {
        "name": "Canada",
        "cities": [
            {"name": "Toronto", "timezone_id": "America/Toronto", "label": "Toronto (ET)"},
            {"name": "Vancouver", "timezone_id": "America/Vancouver", "label": "Vancouver (PT)"},
        ],
    },
    {
        "name": "Brazil",
        "cities": [
            {"name": "São Paulo", "timezone_id": "America/Sao_Paulo", "label": "São Paulo (BRT)"},
        ],
    },
    {
        "name": "South Africa",
        "cities": [
            {"name": "Johannesburg", "timezone_id": "Africa/Johannesburg", "label": "Johannesburg (SAST)"},
        ],
    },
    {
        "name": "Kenya",
        "cities": [
            {"name": "Nairobi", "timezone_id": "Africa/Nairobi", "label": "Nairobi (EAT)"},
        ],
    },
    {
        "name": "Djibouti",
        "cities": [
            {"name": "Djibouti City", "timezone_id": "Africa/Djibouti", "label": "Djibouti City (EAT)"},
        ],
    },
    {
        "name": "Ethiopia",
        "cities": [
            {"name": "Addis Ababa", "timezone_id": "Africa/Addis_Ababa", "label": "Addis Ababa (EAT)"},
        ],
    },
    {
        "name": "Somalia",
        "cities": [
            {"name": "Mogadishu", "timezone_id": "Africa/Mogadishu", "label": "Mogadishu (EAT)"},
        ],
    },
]


def list_timezone_options():
    return TIMEZONE_COUNTRIES


def find_city(country_name, city_name):
    country_name = (country_name or "").strip()
    city_name = (city_name or "").strip()
    for country in TIMEZONE_COUNTRIES:
        if country["name"] == country_name:
            for city in country["cities"]:
                if city["name"] == city_name:
                    return country["name"], city
    return None, None


def is_valid_timezone_selection(country_name, city_name, timezone_id):
    _, city = find_city(country_name, city_name)
    if not city:
        return False
    return city["timezone_id"] == (timezone_id or "").strip()
