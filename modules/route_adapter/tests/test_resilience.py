import common  # noqa: F401
import unittest

from resilience import CircuitBreaker, IdempotencyStore, RetryPolicy


class ResilienceTests(unittest.TestCase):
    def test_circuit_breaker_opens_on_high_error_rate(self):
        breaker = CircuitBreaker(open_seconds=5.0)
        for _ in range(3):
            self.assertTrue(breaker.allow())
        for _ in range(5):
            breaker.record(True)
        self.assertFalse(breaker.allow())

    def test_circuit_breaker_recovers_after_window(self):
        breaker = CircuitBreaker(open_seconds=0.0)
        breaker.record(True)
        breaker.record(True)
        breaker.record(False)
        self.assertTrue(breaker.allow())

    def test_idempotency_replay(self):
        store = IdempotencyStore(window_hours=24)
        store.put("k1", {"routes": []})
        self.assertEqual(store.get("k1"), {"routes": []})
        self.assertEqual(len(store), 1)

    def test_retry_policy_defaults(self):
        policy = RetryPolicy()
        self.assertEqual(policy.max_retries, 2)
        self.assertEqual(policy.connect_timeout, 1.0)
        self.assertEqual(policy.read_timeout, 2.0)


if __name__ == "__main__":
    unittest.main()