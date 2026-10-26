"""Independent brute-force reference for shipping-inclusive assignment costs."""
import itertools
import random
import unittest
from src.optimizer import BOMOptimizer


class TestIndependentShippingOracle(unittest.TestCase):
    def test_100_seeded_three_supplier_cases_against_bruteforce(self):
        rng = random.Random(20261026)
        opt = BOMOptimizer()
        shipping = {"mouser": (50, 15), "digikey": (50, 18), "rs": (75, 12)}
        for case in range(100):
            prices = [{d: rng.randint(1, 50) for d in shipping} for _ in range(5)]
            bom = [{"mpn": f"P{i}", "quantity": 1} for i in range(5)]
            catalog = {f"P{i}": {"distributors": {
                d: {"stock": 20, "price_breaks": {1: p}}
                for d, p in prices[i].items()
            }} for i in range(5)}
            expected = float("inf")
            for assignment in itertools.product(shipping, repeat=5):
                subtotals = {
                    d: sum(prices[i][d] for i in range(5) if assignment[i] == d)
                    for d in shipping
                }
                total = sum(subtotals.values()) + sum(
                    0 if subtotal >= shipping[d][0] else shipping[d][1]
                    for d, subtotal in subtotals.items() if subtotal
                )
                expected = min(expected, total)
            actual = opt.optimize_split_source(bom, catalog)
            self.assertEqual(actual["total_cost"], expected, f"case={case}")
            self.assertTrue(actual["is_optimal"])
            self.assertEqual(actual["evaluated_assignments"], 243)

    def test_100_line_search_is_bounded_and_not_certified(self):
        opt = BOMOptimizer()
        suppliers = ("mouser", "digikey", "rs")
        bom = [{"mpn": f"X{i}", "quantity": 1} for i in range(100)]
        catalog = {f"X{i}": {"distributors": {
            d: {"stock": 20, "price_breaks": {1: 2 + (i % 5)}}
            for d in suppliers
        }} for i in range(100)}
        actual = opt.optimize_split_source(bom, catalog)
        self.assertFalse(actual["is_optimal"])
        self.assertEqual(actual["optimization_method"], "bounded_local_search")
        self.assertLessEqual(actual["evaluated_assignments"], 4 * (1 + 8 * 100 * 2))


if __name__ == "__main__":
    unittest.main()
