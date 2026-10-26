import unittest
from src.optimizer import BOMOptimizer


def offer(stock, moq, breaks):
    return {"stock": stock, "moq": moq, "price_breaks": breaks, "currency": "EUR"}


class RepeatedMPNAggregationTests(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()

    def test_single_source_combines_two_small_rows_into_one_minimum_lot(self):
        bom = [{"mpn": "ABC", "quantity": 1}, {"mpn": "abc", "quantity": 1}]
        catalog = {"ABC": {"distributors": {"mouser": offer(10, 10, {10: 2})}}}
        result = self.opt.optimize_single_source(bom, catalog)["mouser"]
        self.assertTrue(result["is_feasible"], result)
        self.assertEqual(result["items_cost"], 20)
        self.assertEqual(result["total_cost"], 35)
        self.assertEqual(sum(p["qty"] for p in result["parts"]), 10)

    def test_single_source_aggregated_quantity_selects_correct_tier(self):
        bom = [{"mpn": "ABC", "quantity": 6}, {"mpn": "ABC", "quantity": 6}]
        catalog = {"ABC": {"distributors": {"mouser": offer(12, 10, {10: 2, 12: 1.5})}}}
        result = self.opt.optimize_single_source(bom, catalog)["mouser"]
        self.assertTrue(result["is_feasible"], result)
        self.assertEqual(result["items_cost"], 18)
        self.assertEqual(result["total_cost"], 33)

    def test_insufficient_stock_does_not_become_false_feasible(self):
        bom = [{"mpn": "ABC", "quantity": 1}, {"mpn": "ABC", "quantity": 1}]
        catalog = {"ABC": {"distributors": {"mouser": offer(9, 10, {10: 2})}}}
        self.assertFalse(self.opt.optimize_single_source(bom, catalog)["mouser"]["is_feasible"])

    def test_distinct_parts_still_pay_each_minimum_lot(self):
        bom = [{"mpn": "ABC", "quantity": 1}, {"mpn": "XYZ", "quantity": 1}]
        catalog = {mpn: {"distributors": {"mouser": offer(10, 10, {10: 2})}}
                   for mpn in ("ABC", "XYZ")}
        result = self.opt.optimize_single_source(bom, catalog)["mouser"]
        self.assertTrue(result["is_feasible"], result)
        self.assertEqual(result["items_cost"], 40)
        self.assertEqual(len(result["parts"]), 2)

    def test_forty_independent_consolidated_purchase_oracles(self):
        # Independent closed-form oracle: one purchase per MPN, with MOQ
        # and the applicable price tier selected for the total demand.
        for seed in range(40):
            quantities = [1 + (seed % 5), 1 + ((seed * 3) % 7), 1 + ((seed * 7) % 4)]
            moq = 1 + ((seed * 5) % 9)
            stock = 2 + ((seed * 11) % 23)
            breaks = {5: 3, 10: 2}
            requested = sum(quantities)
            purchased = max(requested, moq, 5)
            price = 2 if purchased >= 10 else 3
            bom = [{"mpn": "ABC", "quantity": q} for q in quantities]
            catalog = {"ABC": {"distributors": {"mouser": offer(stock, moq, breaks)}}}
            result = self.opt.optimize_single_source(bom, catalog)["mouser"]
            if stock >= purchased:
                self.assertTrue(result["is_feasible"], f"seed={seed}: {result}")
                self.assertEqual(result["items_cost"], purchased * price, f"seed={seed}")
                self.assertEqual(sum(row["qty"] for row in result["parts"]), purchased)
            else:
                self.assertFalse(result["is_feasible"], f"seed={seed}: {result}")


if __name__ == "__main__":
    unittest.main()
