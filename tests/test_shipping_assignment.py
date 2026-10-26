import itertools
import unittest
from decimal import Decimal
from src.optimizer import BOMOptimizer


def offer(price):
    return {"stock": 1000, "moq": 1, "price_breaks": {1: price}, "currency": "EUR"}


class TestShippingAwareAssignment(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()

    def test_shipping_threshold_counterexample(self):
        bom = [{"mpn": part, "quantity": 1} for part in "ABC"]
        catalog = {
            "A": {"distributors": {"mouser": offer(10)}},
            "B": {"distributors": {"digikey": offer(48)}},
            "C": {"distributors": {"mouser": offer(1), "digikey": offer(5)}},
        }
        result = self.opt.optimize_split_source(bom, catalog)
        self.assertEqual(result["total_cost"], 78.0)
        self.assertEqual({p["mpn"]: p["distributor"] for p in result["parts"]}["C"], "digikey")
        self.assertTrue(result["is_optimal"])

    def test_exhaustive_oracle_for_small_synthetic_cases(self):
        # Independent exhaustive reference: compare full shipping-inclusive assignments.
        for seed in range(30):
            bom = [{"mpn": f"P{i}", "quantity": 1} for i in range(4)]
            prices = {}
            catalog = {}
            for i in range(4):
                prices[i] = {"mouser": 1 + ((seed * 7 + i * 11) % 32),
                             "digikey": 1 + ((seed * 13 + i * 5) % 35)}
                catalog[f"P{i}"] = {"distributors": {d: offer(p) for d, p in prices[i].items()}}
            expected = min(
                sum(prices[i][assign[i]] for i in range(4))
                + sum(0 if sum(prices[i][assign[i]] for i in range(4) if assign[i] == d) >= 50
                          else (15 if d == "mouser" else 18)
                          for d in set(assign))
                for assign in itertools.product(("mouser", "digikey"), repeat=4)
            )
            actual = self.opt.optimize_split_source(bom, catalog)
            self.assertEqual(actual["total_cost"], float(expected), f"seed={seed}")
            self.assertTrue(actual["is_optimal"])

    def test_unavailable_line_not_misreported_feasible(self):
        bom = [{"mpn": "KNOWN", "quantity": 1}, {"mpn": "MISSING", "quantity": 1}]
        catalog = {"KNOWN": {"distributors": {"mouser": offer(5)}}}
        result = self.opt.optimize_split_source(bom, catalog)
        self.assertFalse(result["is_feasible"])
        self.assertTrue(next(p for p in result["parts"] if p["mpn"] == "MISSING")["unfulfilled"])

    def test_large_search_is_bounded_and_discloses_heuristic(self):
        bom = [{"mpn": f"P{i}", "quantity": 1} for i in range(18)]
        catalog = {f"P{i}": {"distributors": {
            "mouser": offer(2 + (i % 3)), "digikey": offer(3 + (i % 2)),
            "rs": offer(5)}} for i in range(18)}
        result = self.opt.optimize_split_source(bom, catalog)
        self.assertFalse(result["is_optimal"])
        self.assertEqual(result["optimization_method"], "bounded_local_search")
        self.assertEqual(len(result["parts"]), 18)
        self.assertTrue(result["is_feasible"])


if __name__ == "__main__":
    unittest.main()

class TestResultClaims(unittest.TestCase):
    def test_html_report_certifies_only_exact_solution(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from main import generate_html_report
        opt = BOMOptimizer()
        bom = [{"mpn": "A", "quantity": 1}]
        catalog = {"A": {"distributors": {"mouser": offer(10)}}}
        exact = opt.optimize_split_source(bom, catalog)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            generate_html_report({}, exact, bom, SimpleNamespace(_mock_db={}), path)
            self.assertIn("Optimal Total Cost", path.read_text(encoding="utf-8"))
            heuristic = dict(exact, is_optimal=False, is_feasible=True)
            generate_html_report({}, heuristic, bom, SimpleNamespace(_mock_db={}), path)
            self.assertIn("Best Found Total (Not Certified)", path.read_text(encoding="utf-8"))
            incomplete = dict(exact, is_optimal=False, is_feasible=False)
            generate_html_report({}, incomplete, bom, SimpleNamespace(_mock_db={}), path)
            self.assertIn("Partial Cost (Unfulfilled Lines)", path.read_text(encoding="utf-8"))

    def test_web_dashboard_labels_nonoptimal_results(self):
        from pathlib import Path
        html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="split-total-heading"', html)
        self.assertIn("data.split_source.is_optimal ?", html)
        self.assertIn("Best Found Cost (Not Certified)", html)
