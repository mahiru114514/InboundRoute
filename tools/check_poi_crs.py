"""校验种子 POI 坐标画到高德底图上是否落在正确位置。

契约依据：`contracts/mappings.json#/crs_conversion`
    内部主数据 = WGS84；高德瓦片 = GCJ-02；转换由客户端单向完成（WGS84 → GCJ-02）。
    所以种子坐标必须是**真正的 WGS84**，本脚本模拟前端把它转成 GCJ-02 后的落点。

用法：
    python tools/check_poi_crs.py                # 校验当前种子坐标
    python tools/check_poi_crs.py --hint 31.24,121.49
                                                 # 把「从高德地图上量到的 GCJ-02 坐标」
                                                 # 换算成应该填进种子文件的 WGS84 值

背景：这批坐标曾经是 GCJ-02 却标成 WGS84，被前端重复转换，图钉整体偏移约 530 m。
      回归测试见 tests/test_poi_crs.py。
"""
import argparse
import sys
from math import cos, pi, sin, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "modules" / "trip_engine"))

from poi_seed import POIS  # noqa: E402

A = 6378245.0
EE = 0.00669342162296594323


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
    """与 modules/web_workbench/web/map.js#gcj02FromWgs84 等价。"""
    if _out_of_china(lat, lng):
        return lat, lng
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = 1 - EE * sin(radlat) ** 2
    sqrtmagic = sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (A / sqrtmagic * cos(radlat) * pi)
    return lat + dlat, lng + dlng


def wgs84_from_gcj02(g_lat, g_lng):
    """GCJ-02 → WGS84（不动点迭代；正解无闭式）。用于把地图上量到的坐标转成种子值。"""
    lat, lng = g_lat, g_lng
    for _ in range(10):
        f_lat, f_lng = gcj02_from_wgs84(lat, lng)
        lat += g_lat - f_lat
        lng += g_lng - f_lng
    return lat, lng


def metres(lat1, lng1, lat2, lng2):
    dlat = (lat2 - lat1) * 111320.0
    dlng = (lng2 - lng1) * 111320.0 * cos(lat1 / 180.0 * pi)
    return sqrt(dlat * dlat + dlng * dlng)


# 已知地标在**高德底图**上的真实位置（GCJ-02），作为独立基准。
LANDMARKS_GCJ = {
    "外滩": (31.24010, 121.49080, "中山东一路观景平台"),
    "上海博物馆": (31.22845, 121.47515, "人民广场馆，武胜路/龙门路口"),
    "豫园": (31.22730, 121.49260, "湖心亭/九曲桥"),
    "朱家角古镇": (31.11360, 121.05330, "放生桥"),
}

TOLERANCE_M = 400.0


def validate():
    print("种子坐标（WGS84）→ 前端转换 → 高德底图落点")
    print("=" * 78)
    worst = 0.0
    failures = []
    for poi in POIS:
        name = poi["names"]["zh-Hans"]
        coord = poi["coordinate"]
        g_lat, g_lng = gcj02_from_wgs84(coord["lat"], coord["lng"])
        line = (f"{name:<12}种子 {coord['lat']:.6f},{coord['lng']:.6f}"
                f"  →  落点 {g_lat:.6f},{g_lng:.6f}")
        if name in LANDMARKS_GCJ:
            r_lat, r_lng, where = LANDMARKS_GCJ[name]
            d = metres(g_lat, g_lng, r_lat, r_lng)
            worst = max(worst, d)
            ok = d < TOLERANCE_M
            if not ok:
                failures.append(name)
            line += f"   偏差 {d:>5.0f} m  {'OK' if ok else '超限'}"
            line += f"  （基准：{where}）"
        print(line)

    print("-" * 78)
    print(f"最大偏差 {worst:.0f} m（阈值 {TOLERANCE_M:.0f} m，基准点本身有几十米不确定度）")
    if failures:
        print(f"\n超限：{'、'.join(failures)}")
        print("排查方向：种子坐标是不是从高德/百度地图直接抄来的（那是 GCJ-02/BD-09，不是 WGS84）？")
        print("          真值可用 --hint 反解。")
        return 1
    print("全部通过。")
    return 0


def hint(text):
    """把从高德底图上量到的 GCJ-02 坐标，换算成应填进种子的 WGS84 值。"""
    try:
        lat_s, lng_s = text.split(",")
        g_lat, g_lng = float(lat_s), float(lng_s)
    except ValueError:
        print("格式应为 纬度,经度，例如 --hint 31.2397,121.49")
        return 2
    w_lat, w_lng = wgs84_from_gcj02(g_lat, g_lng)
    back_lat, back_lng = gcj02_from_wgs84(w_lat, w_lng)
    drift = metres(g_lat, g_lng, back_lat, back_lng)
    print(f"高德底图上量到的坐标（GCJ-02）：{g_lat}, {g_lng}")
    print(f"应填进种子的值（WGS84）：        {round(w_lat, 6)}, {round(w_lng, 6)}")
    print(f"回代校验漂移：{drift:.4f} m")
    return 0


def main():
    parser = argparse.ArgumentParser(description="校验/换算种子 POI 坐标")
    parser.add_argument("--hint", metavar="LAT,LNG",
                        help="把高德底图上的 GCJ-02 坐标反解为应填进种子的 WGS84 值")
    args = parser.parse_args()
    return hint(args.hint) if args.hint else validate()


if __name__ == "__main__":
    sys.exit(main())
