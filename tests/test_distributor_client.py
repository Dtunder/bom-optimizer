import os
import random
import unittest
from pathlib import Path
from unittest.mock import patch

from src.distributor_client import DEFAULT_CACHE_FILE, DistributorClient


class TestDistributorClient(unittest.TestCase):
    def test_default_cache_is_repo_relative(self):
        with patch.dict(os.environ):
            os.environ.pop("BOM_CACHE_FILE", None)
            client = DistributorClient(cache_enabled=False)

        expected = Path(__file__).resolve().parents[1] / "cache" / "distributor_cache.json"
        self.assertEqual(DEFAULT_CACHE_FILE, expected)
        self.assertEqual(client.cache_file, expected)

    def test_cache_file_environment_override_is_used(self):
        override = Path(__file__).resolve().parents[1] / ".test-cache" / "cache.json"
        with patch.dict(os.environ, {"BOM_CACHE_FILE": str(override)}):
            client = DistributorClient()
            client.query_part("CACHE-OVERRIDE-PART")

        try:
            self.assertEqual(client.cache_file, override)
            self.assertTrue(override.exists())
        finally:
            if override.exists():
                override.unlink()
            if override.parent.exists() and not any(override.parent.iterdir()):
                override.parent.rmdir()

    def test_fallback_data_is_per_mpn_deterministic_and_rng_isolated(self):
        random_state = random.getstate()
        first_client = DistributorClient(cache_enabled=False)
        first_client.query_part("UNRELATED-PART")
        first = first_client.query_part("GENERIC-MPN-42")
        second = DistributorClient(cache_enabled=False).query_part("GENERIC-MPN-42")

        self.assertEqual(first, second)
        self.assertEqual(random.getstate(), random_state)


if __name__ == "__main__":
    unittest.main()
