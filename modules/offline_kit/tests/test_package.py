import common  # noqa: F401
import json
import os
import unittest
from copy import deepcopy

from package import CAPACITY_MB, OfflinePackager, is_stale

_EXAMPLE = os.path.join(common.WORKSPACE, "contracts", "examples", "route_transit_transfer.json")


def _route():
    with open(_EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


class PackageTests(unittest.TestCase):
    def test_old_short_english_line_name_gains_the_missing_terminal_pair(self):
        trip = self._trip()
        ride = trip['days'][0]['ordered_stops'][0]['transit_from_previous']['segments'][0]
        ride['line'] = {'code':'889', 'name_zh':'889路(尚泰路乐高路--泸定路同普路)', 'name_en':'Bus 889'}
        ride['direction'] = None
        ride['alight']['station_name_zh'] = '天山西路福泉路'
        line = OfflinePackager().build(trip)['days'][0]['stops'][0]['stations'][0]['lines'][0]
        self.assertEqual(line['name_en'], 'Bus 889 (Shangtai Road / Legao Road — Luding Road / Tongpu Road)')
        self.assertNotIn('direction_en', line)
        ride['line']['name_en'] = 'Verified operator name'
        line = OfflinePackager().build(trip)['days'][0]['stops'][0]['stations'][0]['lines'][0]
        self.assertEqual(line['name_en'], 'Verified operator name (Shangtai Road / Legao Road — Luding Road / Tongpu Road)')

    def test_partly_translated_snapshot_still_completes_line_and_access_names(self):
        trip = self._trip()
        ride = trip['days'][0]['ordered_stops'][0]['transit_from_previous']['segments'][0]
        ride['line'] = {'name_zh':'地铁2号线(浦东1号2号航站楼--虹桥2号航站楼)'}
        ride['direction'] = {'name_zh':'往虹桥2号航站楼方向'}
        ride['board'].update(access_name_zh='1号口', access_name_en='1号口')
        stop = OfflinePackager().build(trip)['days'][0]['stops'][0]
        self.assertEqual(stop['stations'][0]['lines'][0]['name_en'],
                         'Line 2 (Pudong Airport Terminal 1 & 2 — Hongqiao Airport Terminal 2)')
        self.assertEqual(stop['ask_cards'][0]['args']['access_name_en'], 'Entrance 1')

    def test_legacy_names_and_visible_card_arguments_are_completed_without_mutating_trip(self):
        trip = self._trip()
        route = trip['days'][0]['ordered_stops'][0]['transit_from_previous']
        trip['days'][0]['ordered_stops'][0].update(name_zh='外滩',name_en='外滩')
        route['to'] = {'name_zh': '外滩', 'name_en': '外滩'}
        route['from'] = {'name_zh': '上海图书馆', 'name_en': None}
        ride = route['segments'][0]
        ride['board'].update(station_name_zh='浦东1号2号航站楼', station_name_en=None,
                             access_name_zh='1号口', access_name_en=None, access_no=None)
        ride['alight'].update(station_name_zh='虹桥2号航站楼', station_name_en=None)
        ride['direction'] = {'name_zh': '往虹桥2号航站楼方向', 'name_en': 'Towards 虹桥2号航站楼'}
        route['segments'][2].update(walk_note_zh='步行44米到达浦东1号2号航站楼',
                                    walk_note_en='Walk 44 m to reach 浦东1号2号航站楼')
        original = deepcopy(trip)
        stop = OfflinePackager().build(trip)['days'][0]['stops'][0]
        self.assertEqual(stop['name_en'], 'The Bund')
        self.assertEqual(stop['from']['name_en'], 'Shanghai Library')
        self.assertEqual(stop['stations'][0]['name_en'], 'Pudong Airport Terminal 1 & 2')
        self.assertEqual(stop['stations'][0]['lines'][0]['direction_en'], 'Towards Hongqiao Airport Terminal 2')
        self.assertEqual(next(w for w in stop['walk_segments'] if w['kind']=='walk')['note_en'],
                         'Walk 44 m to reach Pudong Airport Terminal 1 & 2')
        cards = {c['template_key']: c for c in stop['ask_cards']}
        self.assertEqual(cards['poi_arrival']['args']['poi_name_en'], 'The Bund')
        self.assertEqual(cards['station_entrance']['args']['access_name_en'], 'Entrance 1')
        self.assertEqual(trip, original)

    def test_daily_anchors_and_end_transfer_gain_english(self):
        trip = self._trip()
        trip['anchor_hotel'] = {'type':'hotel', 'name_zh':'上海图书馆', 'name_en':None,
                               'coordinate':{'lat':31.2,'lng':121.4,'crs':'WGS84'}}
        trip['days'][0]['end_transit'] = {'to':{'name_zh':'上海图书馆','name_en':None}}
        day = OfflinePackager().build(trip)['days'][0]
        self.assertEqual(day['start_anchor']['name_en'], 'Shanghai Library')
        self.assertEqual(day['end_anchor']['name_en'], 'Shanghai Library')
        self.assertEqual(day['end_transfer']['name_en'], 'Shanghai Library')

    def _trip(self):
        return {
            "trip_id": "trip_1", "version": 7,
            "days": [{"day_index": 1, "date": "2026-10-12", "ordered_stops": [
                {"stop_order": 1, "stop_type": "poi", "poi_id": "sh_poi_00088",
                 "arrival_at": 1791819600, "departure_at": None,
                 "name_zh": "上海博物馆", "name_en": "Shanghai Museum",
                 "transit_from_previous": _route()}]}]
        }

    def test_must_include_fields_present(self):
        payload = OfflinePackager().build(self._trip())
        stop = payload["days"][0]["stops"][0]
        self.assertEqual(stop["arrival_at"], 1791819600)
        self.assertIsNone(stop["departure_at"])
        self.assertTrue(stop["stations"])
        self.assertTrue(stop["stations"][0]["name_zh"])
        self.assertTrue(stop["stations"][0]["name_en"])
        self.assertTrue(stop["stations"][0]["lines"])
        self.assertTrue(any(ap["access_no"] for st in stop["stations"] for ap in st["access_points"]))
        self.assertTrue(stop["walk_segments"])
        self.assertTrue(stop["ask_cards"])

    def test_package_size_under_5mb(self):
        payload = OfflinePackager().build(self._trip())
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.assertLess(size, CAPACITY_MB * 1024 * 1024)

    def test_names_and_mock_source_survive_packaging(self):
        trip = self._trip()
        source = trip['days'][0]['ordered_stops'][0]
        source.pop('name_zh')
        source.pop('name_en')
        source['transit_from_previous']['data_source'] = 'mock'
        source['transit_from_previous']['to'].update(
            name_zh='上海博物馆', name_en='Shanghai Museum')
        stop = OfflinePackager().build(trip)['days'][0]['stops'][0]
        self.assertEqual(stop.get('name_zh'), '上海博物馆')
        self.assertEqual(stop.get('name_en'), 'Shanghai Museum')
        self.assertEqual(stop.get('data_source'), 'mock')

    def test_line_direction_is_carried_into_the_package(self):
        trip = self._trip()
        route = trip["days"][0]["ordered_stops"][0]["transit_from_previous"]
        route["segments"][0]["line"] = {"code": "2", "name_zh": "2 号线", "name_en": "Line 2"}
        route["segments"][0]["direction"] = {"name_zh": "往浦东国际机场方向",
                                             "name_en": "Towards Pudong Int'l Airport"}
        line = OfflinePackager().build(trip)["days"][0]["stops"][0]["stations"][0]["lines"][0]
        self.assertEqual(line["direction_zh"], "往浦东国际机场方向")
        self.assertEqual(line["direction_en"], "Towards Pudong Int'l Airport")

    def test_package_without_direction_still_builds(self):
        # 没有方向数据的线路（老包、旧行程）不能因为多了两个键就崩：缺方向时这两个键必须缺席。
        trip = self._trip()
        trip["days"][0]["ordered_stops"][0]["transit_from_previous"]["segments"][0]["direction"] = None
        stop = OfflinePackager().build(trip)["days"][0]["stops"][0]
        line = stop["stations"][0]["lines"][0]
        self.assertNotIn("direction_zh", line)
        self.assertNotIn("direction_en", line)

    def test_legacy_snapshot_gains_english_line_direction_and_access(self):
        # 修复前算出来的老快照：线路 code 是三方主键、没有 name_en/direction/access_no、
        # 步行指引只有中文。打包时应当补齐英文，用户不重算交通也能拿到可读的问路包。
        trip = self._trip()
        route = trip["days"][0]["ordered_stops"][0]["transit_from_previous"]
        ride = route["segments"][0]
        ride["line"] = {"code": "900000160000",
                        "name_zh": "市域机场线(浦东1号2号航站楼--虹桥2号航站楼)"}
        ride["direction"] = None
        ride["board"]["access_name_zh"] = "1号口"
        ride["board"]["access_no"] = None
        ride["board"]["access_name_en"] = None
        ride["alight"]["station_name_zh"] = "虹桥2号航站楼"
        ride["alight"]["access_name_zh"] = "2号口"
        ride["alight"]["access_no"] = None
        ride["alight"]["access_name_en"] = None
        route["segments"][2]["walk_note_zh"] = "沿浦东机场路步行382米向左前方直行；步行24米右转"
        route["segments"][2]["walk_note_en"] = None

        stop = OfflinePackager().build(trip)["days"][0]["stops"][0]
        # 长数字主键不再进包，线路名与英文名补齐
        self.assertNotIn("900000160000", json.dumps(stop, ensure_ascii=False))
        line = next(item for item in stop["stations"][0]["lines"] if item.get("name_zh"))
        self.assertEqual(line["name_zh"], "市域机场线")
        self.assertEqual(line["name_en"], "Airport Link Line")
        self.assertEqual(line["direction_zh"], "往虹桥2号航站楼方向")
        # 站口编号与英文名从中文名派生
        accesses = [ap for st in stop["stations"] for ap in st["access_points"]]
        self.assertIn({"access_no": "1", "kind": "entrance", "name_zh": "1号口", "name_en": "Entrance 1"}, accesses)
        self.assertIn({"access_no": "2", "kind": "exit", "name_zh": "2号口", "name_en": "Exit 2"}, accesses)
        # 步行指引补齐英文；换乘提示本来就带英文，保持原样
        walk = next(item for item in stop["walk_segments"] if item["kind"] == "walk")
        self.assertEqual(walk["note_en"],
                         "Walk 382 m along Pudong Jichang Road, bear left and continue; Walk 24 m, turn right")
        transfer = next(item for item in stop["walk_segments"] if item["kind"] == "transfer")
        self.assertEqual(transfer["note_en"], "Take indoor escalators")
        # 进站口/出站口问路卡因为有了英文名而恢复
        keys = [card["template_key"] for card in stop["ask_cards"]]
        self.assertIn("station_entrance", keys)

    def test_snapshot_english_is_not_overwritten(self):
        # 快照里已经有英文（重算过的行程）时，打包不得改写它。
        trip = self._trip()
        ride = trip["days"][0]["ordered_stops"][0]["transit_from_previous"]["segments"][0]
        ride["line"]["name_en"] = "Line 2 (Green)"
        ride["direction"] = {"name_zh": "往徐泾东方向", "name_en": "Towards East Xujing"}
        stop = OfflinePackager().build(trip)["days"][0]["stops"][0]
        line = stop["stations"][0]["lines"][0]
        self.assertEqual(line["name_en"], "Line 2 (Green)")
        self.assertEqual(line["direction_zh"], "往徐泾东方向")

    def test_stale_on_version_mismatch(self):
        stale, reason = is_stale(3, 7, generated_at=0, now=0)
        self.assertTrue(stale)
        self.assertEqual(reason, "version_mismatch")

    def test_stale_on_ttl_expired(self):
        stale, reason = is_stale(7, 7, generated_at=0, now=25 * 3600)
        self.assertTrue(stale)
        self.assertEqual(reason, "ttl_expired")

    def test_fresh_package(self):
        stale, reason = is_stale(7, 7, generated_at=0, now=3600)
        self.assertFalse(stale)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
