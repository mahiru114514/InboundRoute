import common  # noqa: F401
import unittest

from cache import CallBudget, TTLCache


class CacheTests(unittest.TestCase):
    def test_ttl_cache_hit_and_miss(self):
        cache = TTLCache()
        self.assertEqual(cache.get("k")[1], False)
        cache.set("k", {"v": 1}, ttl_seconds=1800)
        value, hit = cache.get("k")
        self.assertTrue(hit)
        self.assertEqual(value, {"v": 1})

    def test_call_budget_limits(self):
        budget = CallBudget(4)
        for _ in range(4):
            self.assertTrue(budget.acquire())
        self.assertFalse(budget.acquire())
        self.assertEqual(budget.used, 4)


if __name__ == "__main__":
    unittest.main()