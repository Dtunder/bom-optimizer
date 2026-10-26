import unittest
from src.optimizer import BOMOptimizer


def offer(stock, price=1):
    return {"stock": stock, "moq": 1, "price_breaks": {1: price}, "currency": "EUR"}


class TestSharedStock(unittest.TestCase):
    def setUp(self):
        self.opt = BOMOptimizer()
        self.bom = [{"mpn": "SAME", "quantity": 1}, {"mpn": "SAME", "quantity": 1}]

    def test_single_source_cannot_reuse_one_unit_twice(self):
        catalog = {"SAME": {"distributors": {"mouser": offer(1)}}}
        result = self.opt.optimize_single_source(self.bom, catalog)
        self.assertFalse(result["mouser"]["is_feasible"])
        self.assertEqual(result["mouser"]["unfulfilled"][0]["reason"], "Out of stock")

    def test_split_source_cannot_reuse_one_unit_twice(self):
        catalog = {"SAME": {"distributors": {"mouser": offer(1)}}}
        result = self.opt.optimize_split_source(self.bom, catalog)
        self.assertFalse(result["is_feasible"])
        self.assertEqual(sum(p["distributor"] is not None for p in result["parts"]), 1)

    def test_split_source_uses_independent_supplier_stock(self):
        catalog = {"SAME": {"distributors": {"mouser": offer(1), "digikey": offer(1)}}}
        result = self.opt.optimize_split_source(self.bom, catalog)
        self.assertTrue(result["is_feasible"])
        self.assertEqual({p["distributor"] for p in result["parts"]}, {"mouser", "digikey"})

    def test_stock_two_is_sufficient_for_both_rows(self):
        catalog = {"SAME": {"distributors": {"mouser": offer(2)}}}
        self.assertTrue(self.opt.optimize_single_source(self.bom, catalog)["mouser"]["is_feasible"])
        self.assertTrue(self.opt.optimize_split_source(self.bom, catalog)["is_feasible"])

    def test_independent_exhaustive_shared_stock_oracle(self):
        import itertools
        for seed in range(40):
            bom = [{"mpn": "SAME", "quantity": 1}] * 3 + [{"mpn": "OTHER", "quantity": 1}]
            prices = {
                (mpn, dist): 1 + ((seed * (7 if dist == "mouser" else 11) + (3 if mpn == "SAME" else 13)) % 22)
                for mpn in ("SAME", "OTHER") for dist in ("mouser", "digikey")
            }
            stock = {
                ("SAME", "mouser"): seed % 4, ("SAME", "digikey"): (seed // 3) % 4,
                ("OTHER", "mouser"): 1, ("OTHER", "digikey"): 1,
            }
            catalog = {mpn: {"distributors": {
                dist: offer(stock[(mpn, dist)], prices[(mpn, dist)])
                for dist in ("mouser", "digikey")
            }} for mpn in ("SAME", "OTHER")}
            oracle = None
            for assignment in itertools.product(("mouser", "digikey"), repeat=4):
                used, totals, missing = {}, {}, 0
                for item, dist in zip(bom, assignment):
                    mpn = item["mpn"]
                    key = (mpn, dist)
                    if used.get(key, 0) >= stock[key]:
                        missing += 1
                        continue
                    used[key] = used.get(key, 0) + 1
                    totals[dist] = totals.get(dist, 0) + prices[key]
                cost = sum(totals.values()) + sum(
                    0 if subtotal >= 50 else (15 if dist == "mouser" else 18)
                    for dist, subtotal in totals.items()
                )
                score = (missing, cost)
                oracle = score if oracle is None or score < oracle else oracle
            result = self.opt.optimize_split_source(bom, catalog)
            observed = (sum(p["unfulfilled"] for p in result["parts"] if "unfulfilled" in p), result["total_cost"])
            self.assertEqual(observed, oracle, f"seed={seed}")


if __name__ == "__main__":
    unittest.main()
