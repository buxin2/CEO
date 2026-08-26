"""FedEx zone lookup tests — no shipping APIs."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.fedex_zones import (
    CARRIER,
    COUNTRY_TO_ZONE,
    ZONES,
    lookup_fedex,
    unmapped_iso_countries,
)
from services.iso_countries import COUNTRIES


class FedexZoneTests(unittest.TestCase):
    def test_every_country_mapped(self):
        self.assertEqual(unmapped_iso_countries(), [])
        self.assertEqual(len(COUNTRY_TO_ZONE), len(COUNTRIES))

    def test_sample_destinations(self):
        cases = {
            "IN": ("domestic_india", 1500),
            "GM": ("west_africa", 5200),
            "NG": ("west_africa", 5200),
            "GH": ("west_africa", 5200),
            "SN": ("west_africa", 5200),
            "US": ("north_america", 5500),
            "GB": ("united_kingdom_ireland", 4000),
            "DE": ("western_europe", 4200),
            "AU": ("oceania", 4800),
            "JP": ("east_asia", 3600),
            "AE": ("middle_east", 3800),
        }
        for code, (slug, cents) in cases.items():
            quote = lookup_fedex(code)
            self.assertTrue(quote["available"], code)
            self.assertEqual(quote["carrier"], CARRIER)
            self.assertEqual(quote["zone_slug"], slug)
            self.assertEqual(quote["shipping_cents"], cents)
            self.assertGreater(quote["shipping_cents"], 0)

    def test_gambia_by_name(self):
        quote = lookup_fedex("Gambia")
        self.assertEqual(quote["zone_name"], "West Africa")
        self.assertEqual(quote["shipping_cents"], 5200)

    def test_unknown_country(self):
        quote = lookup_fedex("NotACountry")
        self.assertFalse(quote["available"])
        self.assertEqual(quote["shipping_cents"], 0)

    def test_all_zone_prices_set(self):
        for slug, zone in ZONES.items():
            self.assertGreater(zone["rate_cents"], 0, slug)
            self.assertTrue(zone["countries"], slug)


if __name__ == "__main__":
    unittest.main()
