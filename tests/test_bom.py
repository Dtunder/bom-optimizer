import unittest
import sys
from pathlib import Path

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bom_parser import BOMParser
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher
import src.db as db
import os
import json
from decimal import Decimal

class TestBOMOptimizer(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()
        self.matcher = AlternativeMatcher()
        # Use a temporary test database
        db.DB_PATH = Path(__file__).parent / "test_history.db"
        db.init_db()

    def tearDown(self):
        if db.DB_PATH.exists():
            os.remove(db.DB_PATH)

    def test_currency_conversion(self):
        # Test USD to EUR
        usd_price = Decimal("1.0")
        eur_price = self.opt._convert_to_eur(usd_price, "USD")
        self.assertEqual(eur_price, Decimal("0.9200"))
        
        # Test GBP to EUR
        gbp_price = Decimal("1.0")
        eur_price = self.opt._convert_to_eur(gbp_price, "GBP")
        self.assertEqual(eur_price, Decimal("1.1700"))

    def test_optimizer_price_breaks_with_currency(self):
        price_breaks = {1: 10.0, 10: 8.0}
        # 8.0 USD * 0.92 = 7.36 EUR
        self.assertAlmostEqual(float(self.opt._get_price_for_qty(price_breaks, 12, "USD")), 7.36, places=2)

    def test_alternative_matching_safety_constraints(self):
        catalog = {
            "C0805-100NF-50V-10%": {"footprint": "0805", "description": "CAP CER 100NF 50V 10%"},
            "C0805-100NF-25V-5%": {"footprint": "0805", "description": "CAP CER 100NF 25V 5%"},
            "C0805-100NF-100V-5%": {"footprint": "0805", "description": "CAP CER 100NF 100V 5%"},
            "C0805-100NF-EOL": {"footprint": "0805", "description": "CAP CER 100NF 100V 5%", "lifecycle_status": "EOL"}
        }
        
        # Target: 50V, 10%
        target = {"mpn": "TARGET", "footprint": "0805", "description": "100NF 50V 10%"}
        
        alts = self.matcher.find_alternatives(target, catalog)
        
        # Should NOT include 25V one (lower voltage)
        mpns = [a["mpn"] for a in alts]
        self.assertNotIn("C0805-100NF-25V-5%", mpns)
        
        # Should NOT include EOL part
        self.assertNotIn("C0805-100NF-EOL", mpns)
        
        # Should include 100V 5% (higher voltage, better tolerance)
        self.assertIn("C0805-100NF-100V-5%", mpns)
        self.assertIn("C0805-100NF-50V-10%", mpns)

    def test_unit_normalization(self):
        # Resistance
        self.assertEqual(self.matcher._normalize_value("10K", "resistor"), 10000.0)
        self.assertEqual(self.matcher._normalize_value("1M", "resistor"), 1000000.0)
        self.assertEqual(self.matcher._normalize_value("4.7K", "resistor"), 4700.0)
        self.assertEqual(self.matcher._normalize_value("4K7", "resistor"), 4700.0)
        self.assertEqual(self.matcher._normalize_value("100R", "resistor"), 100.0)
        self.assertEqual(self.matcher._normalize_value("10 Ohm", "resistor"), 10.0)
        
        # Capacitance
        self.assertAlmostEqual(self.matcher._normalize_value("100nF", "capacitor"), 100e-9)
        self.assertAlmostEqual(self.matcher._normalize_value("10uF", "capacitor"), 10e-6)
        self.assertAlmostEqual(self.matcher._normalize_value("22pF", "capacitor"), 22e-12)
        self.assertAlmostEqual(self.matcher._normalize_value("1u", "capacitor"), 1e-6)

    def test_alternative_matching_normalized(self):
        catalog = {
            "R0603-10K": {"footprint": "0603", "description": "RES 10K 1%"},
            "C0402-1U": {"footprint": "0402", "description": "CAP 1UF 25V"}
        }
        
        # Test resistor with different notation
        target_res = {"mpn": "T1", "footprint": "0603", "description": "10000 OHM RESISTOR"}
        alts_res = self.matcher.find_alternatives(target_res, catalog)
        self.assertEqual(alts_res[0]["mpn"], "R0603-10K")
        
        # Test capacitor with different notation
        target_cap = {"mpn": "T2", "footprint": "0402", "description": "1000NF CAP"}
        alts_cap = self.matcher.find_alternatives(target_cap, catalog)
        self.assertEqual(alts_cap[0]["mpn"], "C0402-1U")

    def test_alternative_matching_tolerance_fail(self):
        catalog = {
            "R0603-10K-5%": {"footprint": "0603", "description": "RES 10K 5%"},
            "R0603-10K-0.1%": {"footprint": "0603", "description": "RES 10K 0.1%"}
        }
        # Target: 10K 1%
        target = {"mpn": "TARGET", "footprint": "0603", "description": "10K 1% RES"}
        
        alts = self.matcher.find_alternatives(target, catalog)
        mpns = [a["mpn"] for a in alts]
        
        self.assertNotIn("R0603-10K-5%", mpns)
        self.assertIn("R0603-10K-0.1%", mpns)

    def test_db_persistence(self):
        bom_id = db.save_bom("test.csv", 5)
        self.assertIsNotNone(bom_id)
        
        db.save_history(bom_id, 123.45, {"data": "test"})
        
        history = db.get_recent_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["filename"], "test.csv")
        self.assertEqual(history[0]["total_cost"], 123.45)
        self.assertEqual(history[0]["result"], {"data": "test"})

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
