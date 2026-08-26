"""Modem Pay GMD conversion helpers — no live API calls."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.payment.fx_gmd import quote_gmd
from services.payment.modempay_provider import _stringify_metadata


class ModemPayAmountTests(unittest.TestCase):
    def test_usd_converts_to_whole_dalasi(self):
        quote = quote_gmd(8900, "USD", usd_to_gmd=74.5)
        self.assertEqual(quote["amount"], 6631)
        self.assertEqual(quote["currency"], "GMD")
        self.assertIsInstance(quote["amount"], int)

    def test_gmd_stays_whole_dalasi(self):
        self.assertEqual(quote_gmd(45000, "GMD")["amount"], 450)

    def test_no_fractional_dalasi(self):
        quote = quote_gmd(8999, "USD", usd_to_gmd=74.04)
        self.assertEqual(quote["amount"], int(round(89.99 * 74.04)))
        self.assertEqual(quote["amount"], quote["amount"] // 1)

    def test_metadata_strings(self):
        out = _stringify_metadata({"payment_reference": "PAY1", "store_order_id": 12})
        self.assertEqual(out["store_order_id"], "12")
        self.assertEqual(out["payment_reference"], "PAY1")


if __name__ == "__main__":
    unittest.main()
