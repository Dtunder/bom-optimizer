import unittest
import sys
import os
import json
import html
from pathlib import Path
from decimal import Decimal

# Add project path to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import BOMRequestHandler
from main import generate_html_report
from src.optimizer import BOMOptimizer
from src.distributor_client import DistributorClient

class MockRequest:
    def __init__(self, path):
        self.path = path
        self.headers = {}
    
    def get(self, key, default=None):
        return self.headers.get(key, default)

class TestSecurityAndPrecision(unittest.TestCase):
    def test_path_traversal_logic(self):
        # We simulate the path resolution logic in server.py
        WEB_DIR = Path("web").resolve()
        
        def is_path_safe(request_path):
            clean_path = request_path.lstrip("/")
            file_path = (WEB_DIR / clean_path).resolve()
            try:
                file_path.relative_to(WEB_DIR)
                return True
            except ValueError:
                return False

        # Malicious paths
        self.assertFalse(is_path_safe("/../../etc/passwd"))
        self.assertFalse(is_path_safe("/../web_secret/index.html"))
        
        # Safe paths
        self.assertTrue(is_path_safe("/index.html"))
        self.assertTrue(is_path_safe("css/style.css"))

    def test_html_injection_in_report(self):
        # Create malicious BOM data
        malicious_mpn = '<script>alert("XSS")</script>'
        bom_items = [{"mpn": malicious_mpn, "quantity": 1}]
        
        single_res = {
            "mouser": {"is_feasible": True, "total_cost": 10.0, "shipping_cost": 0.0, "parts": []}
        }
        split_res = {
            "total_cost": 10.0, "items_cost": 10.0, "shipping_cost": 0.0,
            "parts": [{"mpn": malicious_mpn, "qty": 1, "distributor": "mouser", "unit_price": 10.0, "total": 10.0}]
        }
        
        client = DistributorClient()
        output_path = Path("tests/test_report.html")
        
        generate_html_report(single_res, split_res, bom_items, client, output_path)
        
        content = output_path.read_text(encoding="utf-8")
        self.assertIn(html.escape(malicious_mpn), content, "Malicious MPN should be escaped in HTML report")
        self.assertNotIn(malicious_mpn, content, "Malicious MPN should NOT be present in raw form in HTML report")
        
        if output_path.exists():
            os.remove(output_path)

    def test_float_rounding_errors(self):
        opt = BOMOptimizer()
        
        # 0.1 + 0.2 = 0.30000000000000004 in float
        # Let's simulate many small items that could accumulate error
        price_breaks = {"1": 0.1}
        qty = 1
        
        total = 0.0
        for _ in range(3):
            total += 0.1
        
        print(f"Sum of 0.1 * 3: {total}")
        # total is 0.30000000000000004
        
        # If we round only at the end, it might be okay for 2 decimals,
        # but for more items or different numbers, it can drift.
        
        # Better example:
        val = 1.005
        # round(1.005, 2) -> 1.0 in Python (rounds to nearest even)
        # Decimal("1.005").quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) -> 1.01
        
        print(f"round(1.005, 2): {round(1.005, 2)}")
        self.assertEqual(round(1.005, 2), 1.0, "Python's round() uses round-to-even which might not be expected for currency")

if __name__ == "__main__":
    unittest.main()
