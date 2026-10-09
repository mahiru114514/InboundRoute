import common  # noqa: F401
import unittest

from crs import from_wgs84, to_wgs84
from normalize import haversine_meters


class CoordinateTests(unittest.TestCase):
    def test_roundtrip_gcj02_under_50m(self):
        lat, lng = 31.2397, 121.4900
        glat, glng = from_wgs84(lat, lng, "GCJ-02")
        wlat, wlng = to_wgs84(glat, glng, "GCJ-02")
        self.assertLess(haversine_meters(lat, lng, wlat, wlng), 50)

    def test_roundtrip_bd09_under_50m(self):
        lat, lng = 31.2397, 121.4900
        blat, blng = from_wgs84(lat, lng, "BD-09")
        wlat, wlng = to_wgs84(blat, blng, "BD-09")
        self.assertLess(haversine_meters(lat, lng, wlat, wlng), 50)

    def test_wgs84_identity(self):
        self.assertEqual(to_wgs84(31.2, 121.5, "WGS84"), (31.2, 121.5))

    def test_unsupported_crs_raises(self):
        with self.assertRaises(ValueError):
            to_wgs84(31.2, 121.5, "MARS")


if __name__ == "__main__":
    unittest.main()