import unittest
import sys
from pathlib import Path

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bom_parser import BOMParser
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

class TestBOMOptimizer(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()
        self.matcher = AlternativeMatcher()

    def test_bom_parser_normalizes_columns(self):
        parser = BOMParser()
        headers = ["Mfr Part Number", "Quantity", "Description", "Case"]
        header_map = parser._normalize_headers(headers)
        self.assertIn("mpn", header_map)
        self.assertIn("quantity", header_map)
        self.assertIn("footprint", header_map)

    def test_optimizer_price_breaks(self):
        price_breaks = {1: 10.0, 10: 8.0, 100: 5.0}
        self.assertEqual(self.opt._get_price_for_qty(price_breaks, 1), 10.0)
        self.assertEqual(self.opt._get_price_for_qty(price_breaks, 5), 10.0)
        self.assertEqual(self.opt._get_price_for_qty(price_breaks, 12), 8.0)
        self.assertEqual(self.opt._get_price_for_qty(price_breaks, 120), 5.0)

    def test_power_set_optimization_shipping_threshold(self):
        # Scenario: 
        # Part A is cheaper at Mouser, but buying everything at DigiKey hits free shipping.
        bom = [{"mpn": "PART-A", "quantity": 1}, {"mpn": "PART-B", "quantity": 1}]
        part_details = {
            "PART-A": {
                "distributors": {
                    "mouser": {"stock": 100, "price_breaks": {1: 10.0}},   # Cheap part
                    "digikey": {"stock": 100, "price_breaks": {1: 15.0}}   # Expensive part
                }
            },
            "PART-B": {
                "distributors": {
                    "mouser": {"stock": 100, "price_breaks": {1: 30.0}},   # Total 40 < 50 threshold
                    "digikey": {"stock": 100, "price_breaks": {1: 40.0}}   # Total 55 > 50 threshold
                }
            }
        }
        # Mouser: 10 + 30 + 15 shipping = 55
        # DigiKey: 15 + 40 + 0 shipping = 55 (tie in this case, but let's see)
        # Let's adjust Mouser to be slightly more expensive total
        part_details["PART-B"]["distributors"]["mouser"]["price_breaks"] = {1: 35.0} 
        # Mouser: 10 + 35 + 15 = 60
        # DigiKey: 15 + 40 + 0 = 55
        
        result = self.opt.optimize_split_source(bom, part_details)
        self.assertEqual(result["total_cost"], 55.0)
        self.assertEqual(len(result["distributors"]), 1)
        self.assertIn("digikey", result["distributors"])

    def test_alternative_matching_enhanced(self):
        catalog = {
            "C0805-100NF-50V-10%": {"footprint": "0805", "description": "CAP CER 100NF 50V 10%"},
            "C0805-100NF-25V-5%": {"footprint": "0805", "description": "CAP CER 100NF 25V 5%"},
            "R0603-10K-1%": {"footprint": "0603", "description": "RES 10K 1%"}
        }
        
        # Test finding capacitor with voltage match
        alts = self.matcher.find_alternatives(
            {"mpn": "CAP-100NF-50V", "footprint": "0805", "description": "100NF 50V CAP"},
            catalog
        )
        self.assertTrue(len(alts) > 0)
        # Best match should be the 50V one
        self.assertEqual(alts[0]["mpn"], "C0805-100NF-50V-10%")
        self.assertGreater(alts[0]["confidence"], 80)

    def test_footprint_normalization(self):
        self.assertEqual(self.matcher._normalize_footprint("r0805"), "0805")
        self.assertEqual(self.matcher._normalize_footprint("SMD 0603"), "0603")
        self.assertEqual(self.matcher._normalize_footprint("SOIC8"), "SOIC-8")

if __name__ == "__main__":
    unittest.main()
