import unittest

from src.optimizer import BOMOptimizer


class TestMinimumPriceBreakOrder(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()
        self.bom = [{"mpn": "MINLOT", "quantity": 1}]

    def details(self, stock):
        return {"MINLOT": {"distributors": {
            "mouser": {"stock": stock, "moq": 1, "price_breaks": {10: 2.0}}
        }}}

    def test_single_source_orders_at_least_minimum_price_break(self):
        result = self.opt.optimize_single_source(self.bom, self.details(20))["mouser"]
        self.assertTrue(result["is_feasible"])
        self.assertEqual(result["parts"][0]["qty"], 10)
        self.assertEqual(result["items_cost"], 20.0)
        self.assertEqual(result["total_cost"], 35.0)

    def test_split_source_orders_at_least_minimum_price_break(self):
        result = self.opt.optimize_split_source(self.bom, self.details(20))
        self.assertEqual(result["parts"][0]["qty"], 10)
        self.assertEqual(result["items_cost"], 20.0)
        self.assertEqual(result["total_cost"], 35.0)

    def test_stock_below_minimum_price_break_is_unavailable(self):
        single = self.opt.optimize_single_source(self.bom, self.details(5))["mouser"]
        self.assertFalse(single["is_feasible"])
        split = self.opt.optimize_split_source(self.bom, self.details(5))
        self.assertTrue(split["parts"][0]["unfulfilled"])
        self.assertIsNone(split["parts"][0]["distributor"])

    def test_existing_valid_break_quantity_remains_unchanged(self):
        bom = [{"mpn": "MINLOT", "quantity": 12}]
        details = {"MINLOT": {"distributors": {
            "mouser": {"stock": 20, "moq": 1, "price_breaks": {10: 2.0}}
        }}}
        result = self.opt.optimize_split_source(bom, details)
        self.assertEqual(result["parts"][0]["qty"], 12)
        self.assertEqual(result["items_cost"], 24.0)


if __name__ == "__main__":
    unittest.main()
