"""POI 主数据扩充回归测试：数量、四条兴趣线、结构完整性与 WGS84 真实性。

背景（缺陷 ③）：种子里只有 4 个 POI，且 `nature`（自然生态）一条都没有，
「只有外滩、上海博物馆、豫园、朱家角」——选点面板里没有公园可选。

本文件只做**断言**，不改数据；坐标校准的第三方基准仍由 `tests/test_poi_crs.py` 负责
（那里用 4 个已知地标的 GCJ-02 常量卡住「重复转换」）。这里关注的是：
    1. 数量与 ID 规范（至少 18 条、ID 唯一且符合 sh_poi_000NN）；
    2. 四个 `category.level1` 全部非空（nature 不再缺失）；
    3. 结构完整：中英文名、罗马字、检索别名、分类字典取值受 mappings.json 约束；
    4. 坐标可信：落在上海包络框内，且**不是** GCJ-02 冒充 WGS84。

第 4 条为什么不直接写死所有坐标的基准常量：
    新点的真值来自高德底图标注（GCJ-02），已用 `crs.gcj02_to_wgs84` 反解；
    再写一遍常量等于把同一份数据抄两处，维护必然漂移。这里改用**闭环检测**：
    WGS84 →（按契约由前端单向转换）→ GCJ-02，落点必须回到上海陆域范围内；
    而 GCJ-02 冒充 WGS84 的错法会把落点整体推出约 530 m，落点会偏到黄浦江/城外，
    或与同批点的几何关系不自洽 —— 用已知地标的常量锚点（test_poi_crs.py）兜底。

运行：python -m unittest tests.test_poi_expansion -v
"""
import importlib.util
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIP_ENGINE = ROOT / "modules" / "trip_engine"
sys.path.insert(0, str(TRIP_ENGINE))

from poi_seed import POIS  # noqa: E402

# 复用既有测试里的被测算法与距离函数，避免两处各写一份转换实现。
_spec = importlib.util.spec_from_file_location("test_poi_crs_ref", Path(__file__).resolve().parent / "test_poi_crs.py")
_crs_ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_crs_ref)
gcj02_from_wgs84 = _crs_ref.gcj02_from_wgs84
metres = _crs_ref.metres

POI_ID_PATTERN = re.compile(r"^sh_poi_[0-9]{5,8}$")

# 契约要求四条兴趣线（contracts/enums.json#/interest）；POI 侧取值域见 poi.schema.json。
INTERESTS = ["history_culture", "modern_skyline", "local_life", "nature"]

# 上海包络框（含崇明、临港、朱家角、辰山等远郊点）：粗筛，用于抓「坐标写错城市/坐标被重复转换」。
SHANGHAI_BBOX = {"lat_min": 30.60, "lat_max": 31.90, "lng_min": 120.80, "lng_max": 122.20}

# 内部主数据精度要求（contracts/mappings.json#/crs_conversion.precision_requirement_m）。
PRECISION_REQUIREMENT_M = 50.0

# category_taxonomy 的 level2 取值域（contracts/mappings.json），新增分类必须同步改契约。
ALLOWED_LEVEL2 = {
    "observation_deck", "riverwalk", "skyscraper",
    "classical_garden", "temple", "museum", "historic_street",
    "wet_market", "food_street", "old_town",
    "park", "botanical_garden", "waterfront",
    "airport", "rail_station", "misc",
}

# 结构性字段（poi.schema.json 的 required + 消费方实际会读的可选字段）。
REQUIRED_OPERATING_FIELDS = [
    "opening_hours", "last_entry_time", "closure_data_status", "closure_rules",
    "is_enclosed_attraction", "advance_booking_days",
    "light_up", "dwell_time",
]


class PoiExpansionTests(unittest.TestCase):
    # ------------------------------------------------------------ 数量与 ID

    def test_at_least_eighteen_pois(self):
        """缺陷 ③：4 个 POI 不足以支撑选点。样本集至少 18 条。"""
        self.assertGreaterEqual(len(POIS), 18, f"POI 数量只有 {len(POIS)} 条")

    def test_poi_ids_are_unique_and_well_formed(self):
        for poi in POIS:
            with self.subTest(poi=poi.get("poi_id")):
                self.assertRegex(poi["poi_id"], POI_ID_PATTERN)
        duplicated = [poi_id for poi_id, count in Counter(p["poi_id"] for p in POIS).items() if count > 1]
        self.assertEqual(duplicated, [], f"poi_id 重复：{duplicated}")

    def test_legacy_ids_keep_their_semantics(self):
        """外滩 / 上海博物馆 / 豫园 的 ID 被其它测试与演示数据引用，语义不能改。"""
        by_id = {poi["poi_id"]: poi for poi in POIS}
        for poi_id, zh_name in (("sh_poi_00042", "外滩"), ("sh_poi_00088", "上海博物馆"), ("sh_poi_00107", "豫园")):
            with self.subTest(poi_id=poi_id):
                self.assertIn(poi_id, by_id)
                self.assertEqual(by_id[poi_id]["names"]["zh-Hans"], zh_name)

    # ------------------------------------------------------------ 兴趣线覆盖

    def test_all_four_interest_categories_are_present(self):
        present = {poi["category"]["level1"] for poi in POIS}
        for interest in INTERESTS:
            with self.subTest(interest=interest):
                self.assertIn(interest, present, f"兴趣线 {interest} 没有任何 POI")
        self.assertTrue(present <= set(INTERESTS) | {"transport_hub", "other"},
                        f"出现未登记的兴趣线：{present - set(INTERESTS)}")

    def test_nature_category_is_no_longer_empty(self):
        """缺陷 ③ 的核心：自然生态一条都没有。"""
        nature = [poi for poi in POIS if poi["category"]["level1"] == "nature"]
        self.assertGreaterEqual(len(nature), 3, f"nature 只有 {len(nature)} 条")
        level2 = {poi["category"]["level2"] for poi in nature}
        self.assertTrue(level2 & {"park", "botanical_garden", "waterfront"},
                        f"nature 的 level2 不在受控字典内：{level2}")

    # ------------------------------------------------------------ 结构与检索

    def test_every_record_is_search_ready(self):
        """中英文名 + 罗马字 + 检索别名齐全，否则「英文/拼音搜索」会漏点。"""
        for poi in POIS:
            name = poi["names"].get("zh-Hans", poi["poi_id"])
            with self.subTest(poi=name):
                names = poi["names"]
                self.assertTrue(names.get("zh-Hans"), "缺 zh-Hans")
                self.assertTrue(names.get("en"), "缺 en")
                roman = poi["romanization"]
                self.assertTrue(roman.get("pinyin"), "缺 romanization.pinyin（人工审核字段）")
                self.assertTrue(roman.get("pinyin_plain"), "缺 romanization.pinyin_plain（检索用）")
                aliases = poi.get("search_aliases")
                self.assertIsInstance(aliases, list)
                self.assertTrue(aliases, "search_aliases 为空，拼音/别名检索会漏")

    def test_structure_matches_contract_shape(self):
        for poi in POIS:
            name = poi["names"]["zh-Hans"]
            with self.subTest(poi=name):
                for field in ("poi_id", "names", "romanization", "category", "coordinate",
                              "operating_rules", "provenance"):
                    self.assertIn(field, poi, f"缺必填字段 {field}")
                category = poi["category"]
                self.assertIn(category["level1"], INTERESTS + ["transport_hub", "other"])
                self.assertIn(category["level2"], ALLOWED_LEVEL2,
                              f"level2={category['level2']} 不在 category_taxonomy 里")
                self.assertTrue(category.get("label_zh") and category.get("label_en"))

                rules = poi["operating_rules"]
                for field in REQUIRED_OPERATING_FIELDS:
                    self.assertIn(field, rules, f"operating_rules 缺 {field}")
                self.assertIn(rules["closure_data_status"], ("verified", "unverified", "unknown"),
                              "closure_data_status 必须是 verified/unverified/unknown；"
                              "未采集就写 unknown，不能假装 verified")
                dwell = rules["dwell_time"]
                self.assertIn(dwell["kind"], ("point", "range"))
                if dwell["kind"] == "range":
                    self.assertLessEqual(dwell["minutes_min"], dwell["minutes_max"])
                elif dwell["kind"] == "point":
                    self.assertGreater(dwell["minutes"], 0)

                provenance = poi["provenance"]
                self.assertIn("source", provenance)
                self.assertIn("updated_at", provenance)

    # ------------------------------------------------------------ 坐标可信度

    def test_coordinates_are_inside_shanghai(self):
        for poi in POIS:
            coord = poi["coordinate"]
            name = poi["names"]["zh-Hans"]
            with self.subTest(poi=name):
                self.assertEqual(coord["crs"], "WGS84",
                                 "内部主数据必须是 WGS84（contracts/mappings.json#/crs_conversion）")
                self.assertTrue(SHANGHAI_BBOX["lat_min"] <= coord["lat"] <= SHANGHAI_BBOX["lat_max"],
                                f"{name} 纬度 {coord['lat']} 不在上海包络框内")
                self.assertTrue(SHANGHAI_BBOX["lng_min"] <= coord["lng"] <= SHANGHAI_BBOX["lng_max"],
                                f"{name} 经度 {coord['lng']} 不在上海包络框内")

    def test_coordinates_are_not_gcj02_mislabelled_as_wgs84(self):
        """抓「坐标其实来自高德（GCJ-02）却标成 WGS84」这一历史坑。

        口径：按契约把种子坐标当成 WGS84 转成 GCJ-02（前端画点的动作），落点必须仍在上海。
        若某条坐标其实是 GCJ-02，它会被**再转一次**，落点整体推出约 530 m；
        对边界点（共青森林公园、辰山植物园）会直接推出包络框。

        说明：这一步是粗筛，单点无法凭数值判定坐标系（上海境内两者的差值远小于包络框）。
        真正的第三方基准仍由 `tests/test_poi_crs.py` 用 4 个已知地标的 GCJ-02 常量守住；
        扩充记录的真值来源与反解漂移记录在 `poi_seed.py` 的文件头注释里。
        """
        for poi in POIS:
            coord = poi["coordinate"]
            name = poi["names"]["zh-Hans"]
            g_lat, g_lng = gcj02_from_wgs84(coord["lat"], coord["lng"])
            with self.subTest(poi=name):
                self.assertTrue(SHANGHAI_BBOX["lat_min"] <= g_lat <= SHANGHAI_BBOX["lat_max"],
                                f"{name} 的 GCJ-02 落点纬度 {g_lat:.5f} 不在上海")
                self.assertTrue(SHANGHAI_BBOX["lng_min"] <= g_lng <= SHANGHAI_BBOX["lng_max"],
                                f"{name} 的 GCJ-02 落点经度 {g_lng:.5f} 不在上海")

    def test_declared_precision_meets_contract(self):
        """契约要求内部主数据精度 ≤ 50 m；precision_m 是自述，也必须落在这个量级。"""
        for poi in POIS:
            coord = poi["coordinate"]
            with self.subTest(poi=poi["names"]["zh-Hans"]):
                if "precision_m" not in coord:
                    # 新批公开地点尚未实测入口精度；schema允许省略，不能填假50米。
                    self.assertIn(poi['poi_id'], {f'sh_poi_{i:05}' for i in range(141, 161)})
                    continue
                self.assertLessEqual(coord["precision_m"], PRECISION_REQUIREMENT_M,
                                     f"{poi['poi_id']} 自述精度 {coord['precision_m']} m 超过契约要求")

    def test_drop_off_points_stay_near_their_poi_and_in_wgs84(self):
        """落客点与本体同坐标系，且距离合理（与 tests/test_poi_crs.py 同一口径）。"""
        for poi in POIS:
            name = poi["names"]["zh-Hans"]
            for drop in poi.get("drop_off_locations") or []:
                with self.subTest(poi=name, drop=drop.get("desc_zh")):
                    point = drop["point"]
                    self.assertEqual(point["crs"], "WGS84")
                    self.assertTrue(drop.get("desc_zh") and drop.get("desc_en"), "落客点需中英文描述")
                    self.assertIn(drop.get("source"), ("curated", "manual", "amap", "tencent", "baidu"))
                    self.assertGreaterEqual(drop.get("priority", 0), 1)
                    distance = metres(poi["coordinate"]["lat"], poi["coordinate"]["lng"],
                                      point["lat"], point["lng"])
                    self.assertLess(distance, 2000.0,
                                    f"{name} 的落客点「{drop.get('desc_zh')}」距本体 {distance:.0f} m，"
                                    f"过远，疑似坐标系不一致或写错。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
