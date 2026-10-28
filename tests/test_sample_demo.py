import unittest
from pathlib import Path

from src.bom_parser import BOMParser
from src.distributor_client import DistributorClient
from src.optimizer import BOMOptimizer


class TestSampleDemo(unittest.TestCase):
    def setUp(self):
        self.bom = BOMParser().parse(str(Path(__file__).resolve().parents[1] / "sample_bom.csv"))
        self.client = DistributorClient(cache_enabled=False)
        self.details = {
            item["mpn"].upper(): self.client.query_part(item["mpn"])
            for item in self.bom
        }
        self.optimizer = BOMOptimizer()

    def test_sample_has_feasible_split_cheaper_than_single_source(self):
        single = self.optimizer.optimize_single_source(self.bom, self.details)
        feasible_single_costs = [
            result["total_cost"] for result in single.values() if result["is_feasible"]
        ]
        split = self.optimizer.optimize_split_source(self.bom, self.details)

        self.assertTrue(split["is_feasible"], split)
        self.assertTrue(split["is_optimal"], split)
        self.assertTrue(feasible_single_costs)
        self.assertEqual(split["total_cost"], 143.45)
        self.assertEqual(min(feasible_single_costs), 179.50)
        self.assertLess(split["total_cost"], min(feasible_single_costs))

    def test_sample_still_reports_zero_stock_as_unfulfilled(self):
        unavailable = {
            mpn: {
                **details,
                "distributors": {
                    dist: {**offer, "stock": 0}
                    for dist, offer in details["distributors"].items()
                },
            }
            for mpn, details in self.details.items()
        }
        split = self.optimizer.optimize_split_source(self.bom, unavailable)

        self.assertFalse(split["is_feasible"])
        self.assertTrue(any(part.get("unfulfilled") for part in split["parts"]))


if __name__ == "__main__":
    unittest.main()
