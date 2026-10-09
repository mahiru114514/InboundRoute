import common  # noqa: F401
import unittest

from geohash import encode


class GeohashTests(unittest.TestCase):
    def test_precision_length(self):
        self.assertEqual(len(encode(31.2397, 121.49, 7)), 7)
        self.assertEqual(len(encode(31.2397, 121.49, 5)), 5)

    def test_deterministic(self):
        self.assertEqual(encode(31.2397, 121.49, 7), encode(31.2397, 121.49, 7))

    def test_nearby_share_prefix(self):
        a = encode(31.2397, 121.49, 7)
        b = encode(31.2400, 121.4905, 7)
        self.assertEqual(a[:5], b[:5])


if __name__ == "__main__":
    unittest.main()