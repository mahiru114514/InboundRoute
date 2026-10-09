"""trip_engine 集成测试：真实起 HTTP 服务，用 http.client 打接口。

沙箱说明：`Manager` 那种用 `tempfile.TemporaryDirectory` 的测试在受限沙箱里会被拒绝写入，
这里同样使用 TemporaryDirectory（项目既有约定）。
"""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "modules" / "trip_engine"
for candidate in (str(ROOT), str(MODULE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from engine import TripService, build_server  # noqa: E402

TOKEN = "test-token-1234567890"
ARRIVAL_AT = 1791819000     # 2026-10-12 23:30 +08:00（跨零点抵达）
BUND = "sh_poi_00042"
MUSEUM = "sh_poi_00088"


def new_trip_payload(**overrides):
    payload = {
        "user_profile": {"party_composition": "family_kids", "pacing": "balanced",
                         "interests": ["history_culture"], "walking_speed_factor": 1.0},
        "duration_days": 2,
        "start_date": "2026-10-12",
        "daily_start_local": "09:00",
        "anchor_arrival": {"at": ARRIVAL_AT, "location_name": "浦东机场 T2",
                           "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"}},
        "anchor_hotel": {"name_en": "Radisson Collection", "name_zh": "上海宏安瑞士大酒店",
                         "coordinate": {"lat": 31.2335, "lng": 121.4789, "crs": "WGS84"}},
    }
    payload.update(overrides)
    return payload


class TripEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.service = TripService(self.data_dir)
        self.server = build_server(self.service, TOKEN, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    # ------------------------------------------------------------ 辅助

    def test_missing_day_cap_uses_balanced_default(self):
        for cap in (None, 0):
            day = {"day_status": "partial", "ordered_stops": [{}], "poi_cap": cap}
            self.service._refresh_day_status(day)
            self.assertEqual(day["day_status"], "partial")
            day["ordered_stops"] *= 4
            self.service._refresh_day_status(day)
            self.assertEqual(day["day_status"], "fulfilled")

    def test_missing_day_cap_uses_balanced_default(self):
        for cap in (None, 0):
            day = {"day_status": "partial", "ordered_stops": [{}], "poi_cap": cap}
            self.service._refresh_day_status(day)
            self.assertEqual(day["day_status"], "partial")
            day["ordered_stops"] *= 4
            self.service._refresh_day_status(day)
            self.assertEqual(day["day_status"], "fulfilled")

    def call(self, method, path, body=None, token=TOKEN, headers=None):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        merged = {**(headers or {})}
        if token:
            merged["X-Module-Token"] = token
        if payload is not None:
            merged["Content-Type"] = "application/json"
        self.client.request(method, path, body=payload, headers=merged)
        response = self.client.getresponse()
        raw = response.read()
        return response.status, (json.loads(raw.decode("utf-8")) if raw else None)

    def make_trip(self, **overrides):
        status, envelope = self.call("POST", "/trips", new_trip_payload(**overrides))
        self.assertEqual(status, 201, envelope)
        return envelope["data"]

    # ------------------------------------------------------------ 健康检查与鉴权

    def test_health_is_open_and_reports_poi_source(self):
        status, envelope = self.call("GET", "/health", token=None)
        self.assertEqual(status, 200)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["data"]["module_id"], "trip_engine")
        self.assertTrue(envelope["data"]["ready"])
        self.assertIn("poi_seed", envelope["data"]["poi_source"])

    def test_other_endpoints_require_token(self):
        status, envelope = self.call("GET", "/pois", token=None)
        self.assertEqual(status, 403)
        self.assertEqual(envelope["error"]["code"], "FORBIDDEN")
        status, _ = self.call("GET", "/pois", token="wrong-token")
        self.assertEqual(status, 403)

    def test_host_header_is_checked(self):
        status, _ = self.call("GET", "/pois", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    # ------------------------------------------------------------ 创建行程

    def test_create_trip_derives_fields(self):
        trip = self.make_trip()
        self.assertRegex(trip["trip_id"], r"^trip_[0-9a-f]{12}$")
        self.assertEqual(trip["version"], 1)
        self.assertEqual(trip["timezone"], "Asia/Shanghai")
        self.assertEqual(trip["status"], "draft")
        # T_start = T_arrival + 90min（默认缓冲）
        self.assertEqual(trip["anchor_arrival"]["activity_start_at"], ARRIVAL_AT + 90 * 60)
        self.assertEqual(trip["anchor_arrival"]["border_buffer_minutes"], 90)
        # 派生偏好
        self.assertEqual(trip["user_profile"]["party_walk_multiplier"], 1.3)
        self.assertTrue(trip["user_profile"]["prefer_taxi"])
        # 天数与每日参数
        self.assertEqual([day["date"] for day in trip["days"]], ["2026-10-12", "2026-10-13"])
        self.assertEqual([day["poi_cap"] for day in trip["days"]], [4, 4])
        self.assertEqual([day["daily_start_local"] for day in trip["days"]], ["09:00", "09:00"])
        # 抵达日标记：抵达时刻是 10-12 23:30，落在 Day 1
        self.assertEqual(trip["days"][0]["day_status"], "arrival_only")
        self.assertEqual(trip["days"][1]["day_status"], "empty")
        self.assertEqual(trip["revision_history"][0]["operation"], "create")

    def test_create_trip_validates_input(self):
        cases = [
            ({"duration_days": 0}, "duration_days"),
            ({"duration_days": 16}, "duration_days"),
            ({"duration_days": "2"}, "duration_days"),
            ({"user_profile": {"party_composition": "robot", "pacing": "balanced"}}, "party_composition"),
            ({"user_profile": {"party_composition": "solo", "pacing": "fast"}}, "pacing"),
            ({"user_profile": {"party_composition": "solo", "pacing": "balanced", "interests": ["food"]}}, "interests"),
            ({"daily_start_local": "9:00"}, "daily_start_local"),
            ({"start_date": "2026/10/12"}, "start_date"),
            ({"anchor_arrival": {"at": 0, "location_name": "x", "coordinate": {"crs": "WGS84"}}}, "anchor_arrival"),
            ({"anchor_hotel": {"name_en": "x"}}, "anchor_hotel"),
        ]
        for overrides, field in cases:
            with self.subTest(field=field):
                status, envelope = self.call("POST", "/trips", new_trip_payload(**overrides))
                self.assertEqual(status, 400, envelope)
                self.assertIn(field, envelope["error"]["message"])

    def test_trip_is_persisted_to_disk(self):
        trip = self.make_trip()
        saved = json.loads((self.data_dir / "trips" / f"{trip['trip_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["trip_id"], trip["trip_id"])
        self.assertEqual(saved["version"], 1)

    # ------------------------------------------------------------ 读取与修改

    def test_get_and_patch_trip(self):
        trip = self.make_trip()
        status, envelope = self.call("GET", f"/trips/{trip['trip_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(envelope["data"]["trip_id"], trip["trip_id"])

        status, envelope = self.call("PATCH", f"/trips/{trip['trip_id']}",
                                     {"user_profile": {"pacing": "packed"}, "daily_start_local": "08:30"},
                                     headers={"If-Match": "1"})
        self.assertEqual(status, 200, envelope)
        updated = envelope["data"]
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["user_profile"]["pacing"], "packed")
        self.assertEqual([day["poi_cap"] for day in updated["days"]], [6, 6])
        self.assertEqual([day["daily_start_local"] for day in updated["days"]], ["08:30", "08:30"])
        self.assertEqual(updated["revision_history"][-1]["operation"], "update_config")

    def test_patch_departure_time_for_only_one_day(self):
        trip = self.make_trip(duration_days=3)
        for day in trip['days']:
            day['ordered_stops'] = [{'stop_order': 1, 'poi_id': BUND, 'arrival_at': 123,
                'departure_at': 456, 'transit_from_previous': {'duration_seconds': 600}, 'rule_notices': []}]
        self.service.store.save(trip)
        status, envelope = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'days': [{'day_index': 2, 'daily_start_local': '10:30'}]}, headers={'If-Match': '1'})
        self.assertEqual(status, 200, envelope)
        days = envelope['data']['days']
        self.assertEqual([d['daily_start_local'] for d in days], ['09:00', '10:30', '09:00'])
        self.assertIsNone(days[1]['ordered_stops'][0]['transit_from_previous'])
        self.assertIsNone(days[1]['ordered_stops'][0]['arrival_at'])
        self.assertEqual(days[0]['ordered_stops'][0]['arrival_at'], 123)
        self.assertEqual(days[2]['ordered_stops'][0]['transit_from_previous']['duration_seconds'], 600)
        status, loaded = self.call('GET', f"/trips/{trip['trip_id']}")
        self.assertEqual(loaded['data']['days'][1]['daily_start_local'], '10:30')
        status, updated = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'user_profile': {'pacing': 'relaxed'}}, headers={'If-Match': '2'})
        self.assertEqual(status, 200, updated)
        self.assertEqual([d['daily_start_local'] for d in updated['data']['days']], ['09:00', '10:30', '09:00'])


    def test_patch_daily_endpoints_persist_and_invalidate_inherited_days(self):
        trip = self.make_trip(duration_days=4)
        for day in trip['days']:
            day['ordered_stops'] = [{'stop_order': 1, 'poi_id': BUND, 'arrival_at': 123,
                'departure_at': 456, 'transit_from_previous': {'duration_seconds': 600}, 'rule_notices': []}]
        self.service.store.save(trip)
        hotel = {**trip['anchor_hotel'], 'type': 'hotel', 'name_zh': '新酒店', 'name_en': 'New Hotel'}
        status, result = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'days': [{'day_index': 2, 'end_anchor': hotel}]}, headers={'If-Match': '1'})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['data']['days'][1]['end_anchor']['name_zh'], '新酒店')
        self.assertEqual(result['data']['days'][0]['ordered_stops'][0]['arrival_at'], 123)
        for day in result['data']['days'][1:]:
            self.assertIsNone(day['ordered_stops'][0]['transit_from_previous'])
        status, result = self.call('GET', f"/trips/{trip['trip_id']}")
        self.assertEqual(result['data']['days'][1]['end_anchor'], hotel)
        status, result = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'days': [{'day_index': 2, 'end_anchor': None}]})
        self.assertEqual(status, 200, result)
        self.assertIsNone(result['data']['days'][1]['end_anchor'])

    def test_daily_endpoint_invalid_coordinate_batch_is_atomic(self):
        trip = self.make_trip(duration_days=3)
        hotel = {**trip['anchor_hotel'], 'type': 'hotel'}
        for coordinate in [{'lat': 91, 'lng': 121, 'crs': 'WGS84'},
                           {'lat': True, 'lng': 121, 'crs': 'WGS84'},
                           {'lat': 31, 'lng': '121', 'crs': 'WGS84'},
                           {'lat': 31, 'lng': 121, 'crs': 'bad'}]:
            status, result = self.call('PATCH', f"/trips/{trip['trip_id']}", {'days': [
                {'day_index': 2, 'end_anchor': hotel},
                {'day_index': 3, 'start_anchor': {**hotel, 'coordinate': coordinate}}]})
            self.assertEqual(status, 400, result)
            saved = self.service.store.get(trip['trip_id'])
            self.assertEqual(saved['version'], 1)
            self.assertIsNone(saved['days'][1].get('end_anchor'))

    def test_global_hotel_change_preserves_unaffected_daily_routes(self):
        trip = self.make_trip(duration_days=3)
        hotel = {**trip['anchor_hotel'], 'type': 'hotel', 'name_zh': '每日酒店', 'name_en': 'Daily Hotel'}
        for day in trip['days']:
            day['start_anchor'] = hotel
            day['end_anchor'] = hotel
            day['ordered_stops'] = [{'stop_order': 1, 'poi_id': BUND, 'arrival_at': 123,
                'departure_at': 456, 'transit_from_previous': {'duration_seconds': 600}, 'rule_notices': []}]
        self.service.store.save(trip)
        status, result = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'anchor_hotel': {**trip['anchor_hotel'], 'name_zh': '全局酒店', 'name_en': 'Global Hotel'}})
        self.assertEqual(status, 200, result)
        for day in result['data']['days']:
            self.assertEqual(day['ordered_stops'][0]['transit_from_previous']['duration_seconds'], 600)
            self.assertEqual(day['ordered_stops'][0]['arrival_at'], 123)
        status, result = self.call('PATCH', f"/trips/{trip['trip_id']}",
            {'days': [{'day_index': 2, 'start_anchor': None, 'end_anchor': None},
                      {'day_index': 3, 'start_anchor': hotel, 'end_anchor': hotel}]})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['data']['days'][2]['ordered_stops'][0]['arrival_at'], 123,
                         'same explicit endpoints keep the route')

    def test_patch_day_departure_invalid_time_is_atomic(self):
        trip = self.make_trip(duration_days=3)
        for bad in ['9:00', '24:00', None, 900]:
            status, envelope = self.call('PATCH', f"/trips/{trip['trip_id']}",
                {'days': [{'day_index': 2, 'daily_start_local': '10:30'},
                          {'day_index': 3, 'daily_start_local': bad}]})
            self.assertEqual(status, 400, envelope)
            self.assertEqual(self.service.store.get(trip['trip_id'])['version'], 1)
            self.assertEqual(self.service.store.get(trip['trip_id'])['days'][1]['daily_start_local'], '09:00')

    def test_patch_rejects_stale_version(self):
        trip = self.make_trip()
        self.call("PATCH", f"/trips/{trip['trip_id']}", {"daily_start_local": "08:00"},
                  headers={"If-Match": "1"})
        status, envelope = self.call("PATCH", f"/trips/{trip['trip_id']}", {"daily_start_local": "07:00"},
                                     headers={"If-Match": "1"})
        self.assertEqual(status, 409)
        self.assertEqual(envelope["error"]["code"], "VERSION_CONFLICT")
        self.assertEqual(envelope["error"]["details"]["actual"], 2)

    def test_get_unknown_trip_is_404(self):
        status, envelope = self.call("GET", "/trips/trip_nope")
        self.assertEqual(status, 404)
        self.assertEqual(envelope["error"]["code"], "TRIP_NOT_FOUND")

    # ------------------------------------------------------------ POI 查询

    def test_list_and_get_pois(self):
        status, envelope = self.call("GET", "/pois")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(envelope["data"]["total"], 4)
        ids = [item["poi_id"] for item in envelope["data"]["pois"]]
        self.assertIn(BUND, ids)

        status, envelope = self.call("GET", "/pois?category_level1=history_culture")
        self.assertTrue(all(item["category"]["level1"] == "history_culture" for item in envelope["data"]["pois"]))

        status, envelope = self.call("GET", "/pois?keyword=waitan")
        self.assertEqual([item["poi_id"] for item in envelope["data"]["pois"]], [BUND])

        status, envelope = self.call("GET", f"/pois/{MUSEUM}")
        self.assertEqual(status, 200)
        self.assertTrue(envelope["data"]["operating_rules"]["reservation_required"])
        self.assertEqual(envelope["data"]["operating_rules"]["closure_rules"][0]["weekday"], 1)

        status, envelope = self.call("GET", "/pois/sh_poi_99999")
        self.assertEqual(status, 404)
        self.assertEqual(envelope["error"]["code"], "POI_NOT_FOUND")

    # ------------------------------------------------------------ 停靠点

    def test_new_shanghai_poi_search_add_and_reload(self):
        from urllib.parse import urlencode
        for keyword in ('上海博物馆东馆', 'Shanghai Museum East', 'shang hai bo wu guan dong guan'):
            status, result = self.call('GET', '/pois?' + urlencode({'keyword': keyword}))
            self.assertEqual(status, 200)
            self.assertEqual([p['poi_id'] for p in result['data']['pois']], ['sh_poi_00141'])
        trip = self.make_trip()
        status, result = self.call('POST', f"/trips/{trip['trip_id']}/days/2/stops", {'poi_id': 'sh_poi_00141'})
        self.assertEqual(status, 201, result)
        self.assertEqual(result['data']['trip']['days'][1]['ordered_stops'][0]['planned_dwell_minutes'], 180)
        status, reloaded = self.call('GET', f"/trips/{trip['trip_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(reloaded['data']['days'][1]['ordered_stops'][0]['poi_id'], 'sh_poi_00141')

    def test_add_stop_uses_poi_dwell_and_renumbers(self):
        trip = self.make_trip()
        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        self.assertEqual(status, 201, envelope)
        day = envelope["data"]["trip"]["days"][1]
        self.assertEqual([stop["poi_id"] for stop in day["ordered_stops"]], [BUND])
        stop = day["ordered_stops"][0]
        self.assertEqual(stop["stop_type"], "poi")
        self.assertEqual(stop["planned_dwell_minutes"], 90)      # 区间下界
        self.assertIsNone(stop["arrival_at"])                    # 时间轴由 rules_engine 填
        self.assertEqual(day["day_status"], "partial")

        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": MUSEUM})
        day = envelope["data"]["trip"]["days"][1]
        self.assertEqual([stop["stop_order"] for stop in day["ordered_stops"]], [1, 2])
        self.assertEqual(day["ordered_stops"][1]["planned_dwell_minutes"], 120)
        self.assertEqual(envelope["data"]["trip"]["revision_history"][-1]["operation"], "add_stop")

    def test_add_stop_accepts_time_or_minutes_for_dwell(self):
        trip = self.make_trip()
        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"poi_id": BUND, "planned_dwell_minutes": "02:00"})
        self.assertEqual(status, 201, envelope)
        self.assertEqual(envelope["data"]["trip"]["days"][1]["ordered_stops"][0]["planned_dwell_minutes"], 120)

    def test_add_stop_rejects_duplicate_and_unknown(self):
        trip = self.make_trip()
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        self.assertEqual(status, 400)
        self.assertIn("已在这一天里", envelope["error"]["message"])

        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": "sh_poi_99999"})
        self.assertEqual(status, 404)

        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/9/stops", {"poi_id": BUND})
        self.assertEqual(status, 404)
        self.assertIn("Day 9 不存在", envelope["error"]["message"])

    def test_pacing_warning_when_over_cap(self):
        trip = self.make_trip(user_profile={"party_composition": "solo", "pacing": "relaxed"})
        pois = ["sh_poi_00042", "sh_poi_00088", "sh_poi_00107"]
        for index, poi_id in enumerate(pois):
            status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": poi_id})
            self.assertEqual(status, 201, envelope)
        self.assertIn("pacing_warning", envelope["data"])
        self.assertIn("建议上限", envelope["data"]["pacing_warning"])
        self.assertEqual(envelope["data"]["trip"]["days"][1]["day_status"], "fulfilled")

    def test_reorder_requires_same_stop_set(self):
        trip = self.make_trip()
        for poi_id in (BUND, MUSEUM, "sh_poi_00107"):
            self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": poi_id})

        # 只挪动未锁定点的相对顺序是允许的
        status, envelope = self.call("PUT", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"stop_order": [MUSEUM, BUND, "sh_poi_00107"]})
        self.assertEqual(status, 200, envelope)
        self.assertEqual([stop["poi_id"] for stop in envelope["data"]["trip"]["days"][1]["ordered_stops"]],
                         [MUSEUM, BUND, "sh_poi_00107"])
        self.assertEqual([stop["stop_order"] for stop in envelope["data"]["trip"]["days"][1]["ordered_stops"]],
                         [1, 2, 3])

        # 新顺序与当日集合不一致要被拒绝
        status, envelope = self.call("PUT", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"stop_order": [MUSEUM, BUND]})
        self.assertEqual(status, 400)
        self.assertIn("集合一致", envelope["error"]["message"])

        # 重复项也要被拒绝
        status, envelope = self.call("PUT", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"stop_order": [MUSEUM, MUSEUM, "sh_poi_00107"]})
        self.assertEqual(status, 400)

    def test_move_to_evening_inserts_before_trailing_locked(self):
        trip = self.make_trip()
        for poi_id in (BUND, MUSEUM):
            self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": poi_id})
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": "sh_poi_00107"})
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": "sh_poi_00119", "locked": True})

        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops/evening", {"poi_id": BUND})
        self.assertEqual(status, 200, envelope)
        order = [stop["poi_id"] for stop in envelope["data"]["trip"]["days"][1]["ordered_stops"]]
        self.assertEqual(order, [MUSEUM, "sh_poi_00107", BUND, "sh_poi_00119"])
        self.assertEqual(envelope["data"]["trip"]["revision_history"][-1]["operation"], "move_to_evening")

        # locked 点不能移动
        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops/evening",
                                     {"poi_id": "sh_poi_00119"})
        self.assertEqual(status, 400)
        self.assertIn("固定", envelope["error"]["message"])

    def test_locked_only_constrains_relative_order(self):
        """locked 点能被别的点绕过（绝对位置可变），但两个 locked 点的相对顺序不能变。"""
        trip = self.make_trip()
        for poi_id, locked in ((BUND, False), (MUSEUM, True), ("sh_poi_00107", True)):
            status, envelope = self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops",
                                         {"poi_id": poi_id, "locked": locked})
            self.assertEqual(status, 201, envelope)

        # 把未锁定的外滩挪到最后 → locked 点绝对位置前移，相对顺序不变，允许
        status, envelope = self.call("PUT", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"stop_order": [MUSEUM, "sh_poi_00107", BUND]})
        self.assertEqual(status, 200, envelope)
        self.assertEqual([stop["poi_id"] for stop in envelope["data"]["trip"]["days"][1]["ordered_stops"]],
                         [MUSEUM, "sh_poi_00107", BUND])

        # 交换两个 locked 点的相对顺序 → 拒绝
        status, envelope = self.call("PUT", f"/trips/{trip['trip_id']}/days/2/stops",
                                     {"stop_order": ["sh_poi_00107", MUSEUM, BUND]})
        self.assertEqual(status, 400)
        self.assertIn("相对顺序", envelope["error"]["message"])

    def test_remove_stop_and_invalidate_timeline(self):
        trip = self.make_trip()
        for poi_id in (BUND, MUSEUM):
            self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": poi_id})
        status, envelope = self.call("DELETE", f"/trips/{trip['trip_id']}/days/2/stops/{BUND}")
        self.assertEqual(status, 200, envelope)
        day = envelope["data"]["trip"]["days"][1]
        self.assertEqual([stop["poi_id"] for stop in day["ordered_stops"]], [MUSEUM])
        self.assertEqual(day["ordered_stops"][0]["stop_order"], 1)
        self.assertIsNone(day["ordered_stops"][0]["arrival_at"])

        status, envelope = self.call("DELETE", f"/trips/{trip['trip_id']}/days/2/stops/{BUND}")
        self.assertEqual(status, 400)

    def test_unknown_route_and_bad_json(self):
        status, envelope = self.call("GET", "/nope")
        self.assertEqual(status, 404)
        self.client.request("POST", "/trips", body=b"{not json", headers={"X-Module-Token": TOKEN})
        response = self.client.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 400)
        self.assertIn("JSON", payload["error"]["message"])


    def test_patch_days_writes_notices_and_confirms(self):
        trip = self.make_trip()
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        notice = {
            "rule_id": "rule_01_closure", "severity": "hard", "outcome": "confirmed_proceed",
            "channel": "modal_confirm", "message_key": "rule.closure.confirm",
            "message_args": {"poi_name": "The Bund", "weekday": "Monday"},
            "confirmed_at": 1791819700, "raised_at": 1791819650, "expires_on_reorder": True,
        }
        status, envelope = self.call("PATCH", f"/trips/{trip['trip_id']}", {
            "days": [{"day_index": 2,
                      "ordered_stops": [{"stop_order": 1, "rule_notices": [notice]}]}],
        })
        self.assertEqual(status, 200, envelope)
        day = envelope["data"]["days"][1]
        self.assertEqual(day["ordered_stops"][0]["rule_notices"][0]["outcome"], "confirmed_proceed")
        self.assertEqual(envelope["data"]["revision_history"][-1]["operation"], "confirm_conflict")

    # ------------------------------------------------------------ 锚点候选清单

    def test_anchors_are_served_from_backend_not_frontend(self):
        """口岸/住宿清单必须由后端供给，且比原来写死在前端的 6+6 更多。"""
        status, envelope = self.call("GET", "/anchors")
        self.assertEqual(status, 200, envelope)
        data = envelope["data"]
        self.assertGreaterEqual(len(data["hubs"]), 7, data["hubs"])
        self.assertGreaterEqual(len(data["hotels"]), 7, data["hotels"])
        self.assertEqual(data["coordinate_system"], "WGS84")
        for anchor in data["hubs"] + data["hotels"]:
            for field in ("id", "name_zh", "name_en", "name_pinyin", "lat", "lng", "coordinate_source"):
                self.assertIn(field, anchor, anchor)
            self.assertIn(anchor["coordinate_source"], ("curated", "approximate"), anchor)

    def test_anchors_keyword_matches_pinyin_and_alias(self):
        for keyword, expected in (("heping", "hotel_peace"),
                                  ("fairmont", "hotel_peace"),
                                  ("shangri-la", "hotel_pudong_shangrila"),
                                  ("hongqiao", None)):
            status, envelope = self.call("GET", f"/anchors?keyword={keyword}")
            self.assertEqual(status, 200, envelope)
            data = envelope["data"]
            ids = [item["id"] for item in data["hotels"] + data["hubs"]]
            if expected:
                self.assertIn(expected, ids, {keyword: ids})
            else:
                self.assertGreaterEqual(len(data["hubs"]), 2, {keyword: ids})

    def test_anchor_departure_round_trips(self):
        """契约 anchor_departure 以前前端没有入口；写入后必须原样读回，供最后一段路线使用。"""
        departure = {"at": ARRIVAL_AT + 4 * 86400, "location_name": "浦东国际机场 T2",
                     "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"},
                     "is_international": False}
        trip = self.make_trip(anchor_departure=departure)
        self.assertEqual(trip["anchor_departure"]["location_name"], "浦东国际机场 T2")
        self.assertEqual(trip["anchor_departure"]["at"], departure["at"])
        self.assertFalse(trip["anchor_departure"]["is_international"])
        self.assertEqual(trip["anchor_departure"]["hub_buffer_minutes"], 180)   # 契约默认
        status, envelope = self.call("GET", f"/trips/{trip['trip_id']}")
        self.assertEqual(status, 200, envelope)
        self.assertEqual(envelope["data"]["anchor_departure"], trip["anchor_departure"])

    def test_anchor_departure_defaults_to_null_and_is_optional(self):
        trip = self.make_trip()
        self.assertIsNone(trip["anchor_departure"])

    def test_anchor_departure_rejects_bad_payload(self):
        status, envelope = self.make_trip_bad(anchor_departure={"at": "not-a-number",
                                                                "location_name": "浦东机场",
                                                                "coordinate": {"lat": 1, "lng": 2, "crs": "WGS84"}})
        self.assertEqual(status, 400, envelope)
        self.assertIn("anchor_departure.at", envelope["error"]["message"])

    def make_trip_bad(self, **overrides):
        return self.call("POST", "/trips", new_trip_payload(**overrides))

    # ------------------------------------------------------------ 预校验 / 删除 / 复制

    def test_validate_does_not_persist_anything(self):
        """预校验必须只校验不落盘 —— 否则「先校验再创建」等于创建了两次。"""
        before = self.service.store.list_trips()
        status, envelope = self.call("POST", "/trips:validate", new_trip_payload())
        self.assertEqual(status, 200, envelope)
        self.assertTrue(envelope["data"]["valid"])
        self.assertEqual(envelope["data"]["dates"], ["2026-10-12", "2026-10-13"])
        self.assertEqual(envelope["data"]["poi_cap"], 4)
        self.assertEqual(self.service.store.list_trips(), before)

    def test_validate_reports_the_same_errors_as_create(self):
        status, envelope = self.call("POST", "/trips:validate",
                                     new_trip_payload(duration_days=99))
        self.assertEqual(status, 400, envelope)
        self.assertIn("duration_days", envelope["error"]["message"])
        self.assertEqual(self.service.store.list_trips(), [])

    def test_delete_trip_removes_it_and_404s_afterwards(self):
        trip = self.make_trip()
        status, envelope = self.call("DELETE", f"/trips/{trip['trip_id']}")
        self.assertEqual(status, 200, envelope)
        self.assertTrue(envelope["data"]["deleted"])
        self.assertEqual(self.service.store.list_trips(), [])
        status, envelope = self.call("GET", f"/trips/{trip['trip_id']}")
        self.assertEqual(status, 404, envelope)

    def test_delete_unknown_trip_is_404_not_silent_success(self):
        status, envelope = self.call("DELETE", "/trips/trip_doesnotexist")
        self.assertEqual(status, 404, envelope)
        self.assertEqual(envelope["error"]["code"], "TRIP_NOT_FOUND")

    def test_duplicate_trip_is_a_new_draft_carrying_the_stops(self):
        trip = self.make_trip()
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        status, envelope = self.call("POST", f"/trips/{trip['trip_id']}:duplicate")
        self.assertEqual(status, 201, envelope)
        copy = envelope["data"]
        self.assertNotEqual(copy["trip_id"], trip["trip_id"])
        self.assertRegex(copy["trip_id"], r"^trip_[0-9a-f]{12}$")
        self.assertEqual(copy["version"], 1)
        self.assertEqual(copy["status"], "draft")
        self.assertEqual([len(day["ordered_stops"]) for day in copy["days"]], [0, 1])
        self.assertEqual([item["operation"] for item in copy["revision_history"]], ["create"])
        # 两份都要在：复制不是搬走
        self.assertIn(trip["trip_id"], self.service.store.list_trips())
        self.assertIn(copy["trip_id"], self.service.store.list_trips())

    def test_duplicate_is_a_deep_copy(self):
        """改副本不能影响原件（浅拷贝会让两份共享同一个 ordered_stops）。"""
        trip = self.make_trip()
        self.call("POST", f"/trips/{trip['trip_id']}/days/2/stops", {"poi_id": BUND})
        _, envelope = self.call("POST", f"/trips/{trip['trip_id']}:duplicate")
        copy_id = envelope["data"]["trip_id"]
        self.call("POST", f"/trips/{copy_id}/days/2/stops", {"poi_id": MUSEUM})
        _, original = self.call("GET", f"/trips/{trip['trip_id']}")
        _, duplicated = self.call("GET", f"/trips/{copy_id}")
        self.assertEqual(len(original["data"]["days"][1]["ordered_stops"]), 1)
        self.assertEqual(len(duplicated["data"]["days"][1]["ordered_stops"]), 2)
    # ------------------------------------------------------------ 跨天移动景点

    def test_move_stop_between_days(self):
        """② 以前只能同一天内上下移动 / 拖拽，不能跨天。"""
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": BUND})
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": MUSEUM})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                     {"to_day_index": 2})
        self.assertEqual(status, 200, envelope)
        moved = envelope["data"]["trip"]
        day1, day2 = moved["days"]
        self.assertEqual([s["poi_id"] for s in day1["ordered_stops"]], [MUSEUM])
        self.assertEqual([s["poi_id"] for s in day2["ordered_stops"]], [BUND])
        # stop_order 必须重新连续编号，不能留下空洞
        self.assertEqual([s["stop_order"] for s in day1["ordered_stops"]], [1])
        self.assertEqual([s["stop_order"] for s in day2["ordered_stops"]], [1])
        # 契约新增的 change_day：跨天移动有专属 operation，不再被记成 reorder
        self.assertEqual(moved["revision_history"][-1]["operation"], "change_day")
        self.assertEqual(moved["revision_history"][-1]["target"], BUND)
        # 两天的时间轴都要作废（两端都变了）
        for day in (day1, day2):
            for stop in day["ordered_stops"]:
                self.assertIsNone(stop["arrival_at"])
                self.assertIsNone(stop["transit_from_previous"])

    def test_move_stop_inserts_at_requested_position(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/2/stops", {"poi_id": MUSEUM})
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": BUND})
        _, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                {"to_day_index": 2, "stop_order": 1})
        self.assertEqual([s["poi_id"] for s in envelope["data"]["trip"]["days"][1]["ordered_stops"]],
                         [BUND, MUSEUM])

    def test_move_stop_rejects_locked_same_day_and_duplicates(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": BUND, "locked": True})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                     {"to_day_index": 2})
        self.assertEqual(status, 400, envelope)
        self.assertIn("locked", envelope["error"]["message"])

        self.call("PATCH", f"/trips/{tid}",
                  {"days": [{"day_index": 1, "ordered_stops": [{"stop_order": 1, "locked": False}]}]})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                     {"to_day_index": 1})
        self.assertEqual(status, 400, envelope)
        self.assertIn("目标日与来源日相同", envelope["error"]["message"])

        self.call("POST", f"/trips/{tid}/days/2/stops", {"poi_id": BUND})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                     {"to_day_index": 2})
        self.assertEqual(status, 400, envelope)
        self.assertIn("已经在 Day 2", envelope["error"]["message"])

    def test_move_stop_rejects_unknown_day_or_poi(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": BUND})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move",
                                     {"to_day_index": 9})
        self.assertEqual(status, 404, envelope)
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{MUSEUM}/move",
                                     {"to_day_index": 2})
        self.assertEqual(status, 400, envelope)
        self.assertIn("没有", envelope["error"]["message"])

    def test_move_stop_requires_target_day(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/1/stops", {"poi_id": BUND})
        status, envelope = self.call("POST", f"/trips/{tid}/days/1/stops/{BUND}/move", {})
        self.assertEqual(status, 400, envelope)
        self.assertIn("to_day_index", envelope["error"]["message"])
    # ------------------------------------------------------------ 创建后修改设定

    def test_patch_extends_and_shrinks_duration(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        status, envelope = self.call("PATCH", f"/trips/{tid}", {"duration_days": 4})
        self.assertEqual(status, 200, envelope)
        days = envelope["data"]["days"]
        self.assertEqual([d["date"] for d in days],
                         ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"])
        self.assertEqual([d["day_index"] for d in days], [1, 2, 3, 4])
        self.assertEqual(envelope["data"]["revision_history"][-1]["operation"], "update_config")

        status, envelope = self.call("PATCH", f"/trips/{tid}", {"duration_days": 2})
        self.assertEqual(status, 200, envelope)
        self.assertEqual([d["day_index"] for d in envelope["data"]["days"]], [1, 2])

    def test_patch_cannot_shrink_away_days_that_hold_stops(self):
        """缩短天数不能静默丢掉已排的点位。"""
        trip = self.make_trip()
        tid = trip["trip_id"]
        self.call("POST", f"/trips/{tid}/days/2/stops", {"poi_id": BUND})
        status, envelope = self.call("PATCH", f"/trips/{tid}", {"duration_days": 1})
        self.assertEqual(status, 400, envelope)
        self.assertIn("丢掉已排的点位", envelope["error"]["message"])
        _, after = self.call("GET", f"/trips/{tid}")
        self.assertEqual(len(after["data"]["days"]), 2)          # 行程没有被改动

    def test_patch_shifts_start_date_and_retags_arrival_day(self):
        trip = self.make_trip()          # 抵达 2026-10-12 23:30 → Day 1 是抵达日
        tid = trip["trip_id"]
        status, envelope = self.call("PATCH", f"/trips/{tid}", {"start_date": "2026-10-13"})
        self.assertEqual(status, 200, envelope)
        days = envelope["data"]["days"]
        self.assertEqual([d["date"] for d in days], ["2026-10-13", "2026-10-14"])
        # 抵达时刻落在 10-12，已不在行程内：不能留下一个「抵达日」标记错误的天
        self.assertEqual([d["day_status"] for d in days], ["empty", "empty"])

    def test_patch_retags_arrival_day_when_arrival_moves(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        moved = ARRIVAL_AT + 86400          # 抵达改到 10-13
        status, envelope = self.call("PATCH", f"/trips/{tid}", {
            "anchor_arrival": {"at": moved, "location_name": "浦东机场 T2",
                               "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"}}})
        self.assertEqual(status, 200, envelope)
        self.assertEqual([d["day_status"] for d in envelope["data"]["days"]],
                         ["empty", "arrival_only"])

    def test_patch_sets_and_clears_anchor_departure(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        departure = {"at": ARRIVAL_AT + 2 * 86400, "location_name": "浦东国际机场 T2",
                     "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"},
                     "is_international": False}
        status, envelope = self.call("PATCH", f"/trips/{tid}", {"anchor_departure": departure})
        self.assertEqual(status, 200, envelope)
        self.assertFalse(envelope["data"]["anchor_departure"]["is_international"])

        status, envelope = self.call("PATCH", f"/trips/{tid}", {"anchor_departure": None})
        self.assertEqual(status, 200, envelope)
        self.assertIsNone(envelope["data"]["anchor_departure"])

    def test_patch_updates_profile_and_daily_start(self):
        trip = self.make_trip()
        tid = trip["trip_id"]
        status, envelope = self.call("PATCH", f"/trips/{tid}", {
            "user_profile": {"party_composition": "solo", "pacing": "packed", "interests": ["nature"]},
            "daily_start_local": "07:30"})
        self.assertEqual(status, 200, envelope)
        data = envelope["data"]
        self.assertEqual(data["user_profile"]["pacing"], "packed")
        self.assertEqual(data["user_profile"]["interests"], ["nature"])
        self.assertFalse(data["user_profile"]["prefer_taxi"])     # solo → 不再优先打车
        self.assertEqual([day["poi_cap"] for day in data["days"]], [6, 6])
        self.assertEqual([day["daily_start_local"] for day in data["days"]], ["07:30", "07:30"])


if __name__ == "__main__":
    unittest.main()
