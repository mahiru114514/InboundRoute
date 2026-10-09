import common  # noqa: F401
import unittest

from degradation import DEGRADATION_MATRIX, degrade, null_out


class DegradationTests(unittest.TestCase):
    def test_route_api(self):
        result = degrade("route_api", "timeout")
        self.assertEqual(result["fallback"], "直线距离粗算")
        self.assertEqual(result["notice_key"], "degraded.direct_orientation")
        self.assertTrue(result["must_notify"])
        self.assertIn("cost", result["null_fields"])

    def test_reverse_geo(self):
        result = degrade("reverse_geo", "timeout")
        self.assertTrue(result["must_notify"])
        self.assertIn("coordinate", result["null_fields"])

    def test_realtime_transit(self):
        result = degrade("realtime_transit", "unsupported_city")
        self.assertIn("使用计划时刻表", result["fallback"])
        self.assertTrue(result["must_notify"])

    def test_rules_data(self):
        result = degrade("rules_data", "closure_data_status=unknown")
        self.assertEqual(result["notice_key"], "rule.closure.data_unknown")
        self.assertTrue(result["must_notify"])

    def test_tiles(self):
        result = degrade("tiles", "load_error")
        self.assertIn("纯文字流程树", result["fallback"])
        self.assertTrue(result["must_notify"])

    def test_null_out_not_zero(self):
        payload = {"cost": 12, "transfer_count": 1, "duration": 100}
        null_out(payload, ["cost", "transfer_count"])
        self.assertIsNone(payload["cost"])
        self.assertIsNone(payload["transfer_count"])
        self.assertEqual(payload["duration"], 100)

    def test_all_five_dependencies_declared(self):
        self.assertEqual(set(DEGRADATION_MATRIX), {"route_api", "reverse_geo",
                                                   "realtime_transit", "rules_data", "tiles"})


if __name__ == "__main__":
    unittest.main()