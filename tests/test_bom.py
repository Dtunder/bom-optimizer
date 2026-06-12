import unittest
import sys
from pathlib import Path

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bom_parser import BOMParser
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

class TestBOMOptimizer(unittest.TestCase):
    def test_bom_parser_normalizes_columns(self):
        parser = BOMParser()
        headers = ["Mfr Part Number", "Quantity", "Description", "Case"]
        header_map = parser._normalize_headers(headers)
        self.assertIn("mpn", header_map)
        self.assertIn("quantity", header_map)
        self.assertIn("footprint", header_map)

    def test_optimizer_price_breaks(self):
        opt = BOMOptimizer()
        price_breaks = {1: 10.0, 10: 8.0, 100: 5.0}
        self.assertEqual(opt._get_price_for_qty(price_breaks, 1), 10.0)
        self.assertEqual(opt._get_price_for_qty(price_breaks, 5), 10.0)
        self.assertEqual(opt._get_price_for_qty(price_breaks, 12), 8.0)
        self.assertEqual(opt._get_price_for_qty(price_breaks, 120), 5.0)

    def test_alternative_matching(self):
        matcher = AlternativeMatcher()
        catalog = {
            "R0805-10K-1%": {"footprint": "0805", "description": "RES SMD 10K Ohm 1%"},
            "R0805-22K-1%": {"footprint": "0805", "description": "RES SMD 22K Ohm 1%"},
            "C0603-100NF-50V": {"footprint": "0603", "description": "CAP CER 100NF"}
        }
        
        # Test finding resistor match with same footprint and value
        alts = matcher.find_alternatives(
            {"mpn": "RES-10K", "footprint": "0805", "description": "Resistor 10K 0805"},
            catalog
        )
        self.assertTrue(len(alts) > 0)
        self.assertEqual(alts[0]["mpn"], "R0805-10K-1%")
        self.assertEqual(alts[0]["confidence"], 90)

if __name__ == "__main__":
    unittest.main()
