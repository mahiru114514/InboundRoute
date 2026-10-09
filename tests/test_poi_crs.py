"""POI 坐标系统回归测试：种子里标称 WGS84 的坐标，画到高德底图上必须落在正确位置。

背景（真实 bug）：种子坐标实际是 GCJ-02，却标成了 `crs: "WGS84"`，
前端按契约又转了一次，4 个图钉全部同方向偏移约 530 m。
这种 bug 肉眼很难判断，所以这里用「已知地标的 GCJ-02 坐标」做锚点卡住它。

为什么断言值写死常量、而不是用同一个算法现算：
    如果断言也用被测算法现算，算法写错时两边一起错，测试会假通过。
    写死常量则形成独立的第三方基准，算法一旦偏离就会红。

运行：python -m unittest tests.test_poi_crs -v
"""
import sys
import unittest
from math import cos, pi, sin, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIP_ENGINE = ROOT / "modules" / "trip_engine"
sys.path.insert(0, str(TRIP_ENGINE))

from poi_seed import POIS  # noqa: E402


# --------------------------------------------------------------------------
# 被测算法：必须与 modules/web_workbench/web/map.js#gcj02FromWgs84 一致
# --------------------------------------------------------------------------
_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lat, lng):
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * sqrt(abs(x))
    ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * sin(y * pi) + 40.0 * sin(y / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * sin(y / 12.0 * pi) + 320.0 * sin(y / 30.0 * pi)) * 2.0 / 3.0
    return ret


def _transform_lng(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * sqrt(abs(x))
    ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * sin(x * pi) + 40.0 * sin(x / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * sin(x / 12.0 * pi) + 300.0 * sin(x / 30.0 * pi)) * 2.0 / 3.0
    return ret


def gcj02_from_wgs84(lat, lng):
    if _out_of_china(lat, lng):
        return lat, lng
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = 1 - _EE * sin(radlat) ** 2
    sqrtmagic = sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * cos(radlat) * pi)
    return lat + dlat, lng + dlng


def metres(lat1, lng1, lat2, lng2):
    dlat = (lat2 - lat1) * 111320.0
    dlng = (lng2 - lng1) * 111320.0 * cos(lat1 / 180.0 * pi)
    return sqrt(dlat * dlat + dlng * dlng)


# 已知地标在**高德底图**上的真实位置（GCJ-02）。这些是独立基准，不参与计算。
LANDMARKS_GCJ = {
    "外滩": (31.24010, 121.49080),
    "上海博物馆": (31.22845, 121.47515),
    "豫园": (31.22730, 121.49260),
    "朱家角古镇": (31.11360, 121.05330),
}

# 允许误差：参考点本身取自地图标注，本身就有几十米量级的不确定度。
TOLERANCE_M = 400.0

BY_NAME = {poi["names"]["zh-Hans"]: poi for poi in POIS}


class PoiCrsTests(unittest.TestCase):
    def test_transform_lands_on_the_real_landmark(self):
        """每个 POI 转成 GCJ-02 后，必须落在高德底图上真实地物的附近。

        这是抓「重复转换 / 漏转换」的核心断言：
        若种子坐标是 GCJ-02 却被当成 WGS84，这里会偏出去约 530 m。
        """
        for name, (r_lat, r_lng) in LANDMARKS_GCJ.items():
            with self.subTest(poi=name):
                poi = BY_NAME[name]
                coord = poi["coordinate"]
                self.assertEqual(coord["crs"], "WGS84",
                                 f"{name} 的内部主数据必须是 WGS84（见 contracts/mappings.json）")
                g_lat, g_lng = gcj02_from_wgs84(coord["lat"], coord["lng"])
                distance = metres(g_lat, g_lng, r_lat, r_lng)
                self.assertLess(
                    distance, TOLERANCE_M,
                    f"{name} 画到高德底图后会偏 {distance:.0f} m。"
                    f"图钉落点 {g_lat:.5f},{g_lng:.5f}，真实位置 {r_lat:.5f},{r_lng:.5f}。"
                    f"常见原因：种子坐标其实是 GCJ-02 却标成了 WGS84（被转换了两次）。")

    def test_all_offsets_are_consistent_not_systematic(self):
        """偏移方向不应呈现「全体同向约 530 m」的系统性特征。

        重复转换的特征是：4 个点全部朝同一个方向偏，且距离几乎一样。
        """
        offsets = []
        for name, (r_lat, r_lng) in LANDMARKS_GCJ.items():
            coord = BY_NAME[name]["coordinate"]
            g_lat, g_lng = gcj02_from_wgs84(coord["lat"], coord["lng"])
            offsets.append((name, (g_lat - r_lat) * 111320.0, (g_lng - r_lng) * 111320.0))

        # 经度方向不应全部同号且量级接近（重复转换时会全部 +500 m 左右）
        lng_offsets = [d_lng for _, _, d_lng in offsets]
        all_same_sign = all(d > 0 for d in lng_offsets) or all(d < 0 for d in lng_offsets)
        magnitude = sum(abs(d) for d in lng_offsets) / len(lng_offsets)
        self.assertFalse(
            all_same_sign and magnitude > 400.0,
            f"检测到系统性经度偏移：{[(n, round(round(d))) for n, _, d in offsets]}。"
            f"这通常是坐标被重复转换的信号。")

    def test_drop_off_points_are_near_their_poi(self):
        """落客点到 POI 本体的距离必须合理，防止两者用了不同坐标系。"""
        for poi in POIS:
            name = poi["names"]["zh-Hans"]
            for drop in poi.get("drop_off_locations") or []:
                with self.subTest(poi=name, drop=drop.get("desc_zh")):
                    main = poi["coordinate"]
                    point = drop["point"]
                    self.assertEqual(point["crs"], "WGS84")
                    distance = metres(main["lat"], main["lng"], point["lat"], point["lng"])
                    self.assertLess(distance, 2000.0,
                                    f"{name} 的落客点「{drop.get('desc_zh')}」距本体 {distance:.0f} m，"
                                    f"过远，疑似坐标系不一致或写错。")

    def test_gcj02_conversion_is_not_a_noop_in_china(self):
        """上海必须发生偏移（~500 m 量级），否则说明转换没生效。"""
        for name in LANDMARKS_GCJ:
            coord = BY_NAME[name]["coordinate"]
            g_lat, g_lng = gcj02_from_wgs84(coord["lat"], coord["lng"])
            shift = metres(coord["lat"], coord["lng"], g_lat, g_lng)
            with self.subTest(poi=name):
                self.assertGreater(shift, 300.0, f"{name} 的 GCJ-02 偏移只有 {shift:.0f} m，转换似乎没生效")
                self.assertLess(shift, 800.0, f"{name} 的 GCJ-02 偏移达 {shift:.0f} m，超出国内正常范围")


if __name__ == "__main__":
    unittest.main(verbosity=2)
