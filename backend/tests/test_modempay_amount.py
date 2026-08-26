"""Modem Pay amount / metadata helpers — no live API calls."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.payment.modempay_provider import _major_amount, _stringify_metadata


class ModemPayAmountTests(unittest.TestCase):
    def test_usd_cents_become_integer_dollars(self):
        self.assertEqual(_major_amount(3499, "USD"), 35)
        self.assertEqual(_major_amount(8700, "USD"), 87)
        self.assertEqual(_major_amount(50, "USD"), 1)

    def test_gmd_same_rule(self):
        self.assertEqual(_major_amount(45000, "GMD"), 450)

    def test_metadata_strings(self):
        out = _stringify_metadata({"payment_reference": "PAY1", "store_order_id": 12})
        self.assertEqual(out["store_order_id"], "12")
        self.assertEqual(out["payment_reference"], "PAY1")


if __name__ == "__main__":
    unittest.main()
