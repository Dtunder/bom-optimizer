import unittest
import sys
import os
import json
import csv
import tempfile
from pathlib import Path

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bom_parser import BOMParser
from src.distributor_client import DistributorClient
from src.optimizer import BOMOptimizer
from src.alternative_matcher import AlternativeMatcher

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.parser = BOMParser()
        self.opt = BOMOptimizer()
        self.client = DistributorClient(cache_enabled=False)
        self.matcher = AlternativeMatcher()

    def test_bom_parser_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tf:
            tf.write("")
            tf_path = tf.name
        
        try:
            with self.assertRaises(ValueError) as cm:
                self.parser.parse_csv(tf_path)
            self.assertIn("empty", str(cm.exception))
        finally:
            os.remove(tf_path)

    def test_bom_parser_missing_headers(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tf:
            tf.write("Something,Else\n1,2")
            tf_path = tf.name
        
        try:
            with self.assertRaises(ValueError) as cm:
                self.parser.parse_csv(tf_path)
            self.assertIn("MPN", str(cm.exception))
        finally:
            os.remove(tf_path)

    def test_bom_parser_non_integer_quantity(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tf:
            tf.write("MPN,Quantity\nPART1,10pcs\nPART2,abc\nPART3,2.5")
            tf_path = tf.name
        
        try:
            items = self.parser.parse_csv(tf_path)
            self.assertEqual(items[0]["quantity"], 10)
            self.assertEqual(items[1]["quantity"], 1) # Fallback in code is 1
            self.assertEqual(items[2]["quantity"], 2) # re.search(r"\d+", "2.5") -> "2"
        finally:
            os.remove(tf_path)

    def test_optimizer_empty_price_breaks(self):
        # Should return 0.0 instead of crashing
        price = self.opt._get_price_for_qty({}, 10)
        self.assertEqual(price, 0.0)

    def test_optimizer_no_stock_feasible(self):
        bom = [{"mpn": "PART1", "quantity": 10}]
        part_details = {
            "PART1": {
                "distributors": {
                    "mouser": {"stock": 5, "price_breaks": {1: 1.0}}
                }
            }
        }
        res = self.opt.optimize_single_source(bom, part_details)
        self.assertFalse(res["mouser"]["is_feasible"])
        self.assertEqual(res["mouser"]["unfulfilled"][0]["reason"], "Out of stock")

    def test_matcher_greedy_regex(self):
        # Description with multiple values
        params = self.matcher._extract_parameters("RES 10K 50V 1% 0805")
        self.assertEqual(params["raw_value"], "10K")
        self.assertEqual(params["voltage"], 50.0)
        self.assertEqual(params["tolerance"], 1.0)

    def test_distributor_client_fallback(self):
        # Querying non-existent part should generate data and not crash
        res = self.client.query_part("UNKNOWN-PART-123")
        self.assertEqual(res["mpn"], "UNKNOWN-PART-123")
        self.assertIn("mouser", res["distributors"])

if __name__ == "__main__":
    unittest.main()
