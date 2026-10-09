"""rules_engine 纯规则层单测：Rule-01~04、时序推演、执行框架（方案 A）。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]        # workspace root
MODULE = Path(__file__).resolve().parents[1]      # modules/rules_engine
for candidate in (str(ROOT), str(MODULE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import rules  # noqa: E402
from rules import (  # noqa: E402
    evaluate_day, build_timeline, rule_01_closure, rule_02_lightup,
    rule_03_spread, rule_04_homogeneous, summarize_render, haversine_km,
    load_contracts, RULE_IDS,
)

NOW = 1791819600
MONDAY = "2026-10-12"
TUESDAY = "2026-10-13"


def make_poi(poi_id="sh_poi_00088", level1="history_culture", level2="museum",
             operating=None, city=None, coordinate=None):
    coordinate = coordinate or {"lat": 31.2300, "lng": 121.4700, "crs": "WGS84"}
    poi = {
        "poi_id": poi_id,
        "names": {"zh-Hans": poi_id, "en": poi_id},
        "category": {"level1": level1, "level2": level2,
                     "label_en": level2, "label_zh": level2},
        "coordinate": coordinate,
        "operating_rules": operating or {
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [], "is_enclosed_attraction": False},
        "provenance": {"source": "manual", "updated_at": 0},
    }
    if city is not None:
        poi["city"] = city
    return poi


def make_stop(poi_id, dwell=90, transit=None, order=1, locked=False):
    return {
        "stop_order": order, "stop_type": "poi", "poi_id": poi_id, "locked": locked,
        "arrival_at": None, "departure_at": None, "user_preferred_arrival_local": None,
        "planned_dwell_minutes": dwell, "transit_from_previous": transit, "rule_notices": [],
    }


def make_day(day_index=1, date=MONDAY, daily_start_local="09:00", stops=None):
    return {"day_index": day_index, "date": date, "day_status": "partial",
            "daily_start_local": daily_start_local, "poi_cap": 6,
            "ordered_stops": stops or []}


def make_trip(days=None, anchor_arrival=None):
    return {
        "trip_id": "trip_test", "version": 1, "status": "draft", "timezone": "Asia/Shanghai",
        "user_profile": {"party_composition": "solo", "pacing": "balanced", "interests": []},
        "anchor_arrival": anchor_arrival or {
            "arrival_at": 1791819000, "activity_start_at": 1791824400,
            "border_buffer_minutes": 90, "location_name": "PVG",
            "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"}},
        "anchor_hotel": {"name_en": "Hotel", "name_zh": "酒店",
                         "coordinate": {"lat": 31.2335, "lng": 121.4789, "crs": "WGS84"}},
        "days": days or [make_day()],
    }


class PerDayStartTests(unittest.TestCase):
    def test_arrival_day_can_start_later_but_not_before_buffer(self):
        activity = rules.date_hhmm_to_utc(MONDAY, '11:00')
        trip = make_trip(anchor_arrival={'activity_start_at': activity})
        self.assertEqual(rules.day_start_utc(trip, make_day(daily_start_local='08:00')), activity)
        self.assertEqual(rules.day_start_utc(trip, make_day(daily_start_local='14:30')),
                         rules.date_hhmm_to_utc(MONDAY, '14:30'))

    def test_cross_midnight_arrival_cannot_start_on_the_previous_date(self):
        activity = rules.date_hhmm_to_utc(TUESDAY, '01:00')
        trip = make_trip(anchor_arrival={'activity_start_at': activity})
        self.assertEqual(rules.day_start_utc(trip, make_day(daily_start_local='23:59')), activity)

    def test_later_days_use_their_own_departure_times(self):
        trip = make_trip()
        self.assertEqual(rules.day_start_utc(trip, make_day(2, TUESDAY, '10:30')),
                         rules.date_hhmm_to_utc(TUESDAY, '10:30'))


class Rule01Tests(unittest.TestCase):
    def _weekly_poi(self):
        return make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}],
            "is_enclosed_attraction": True})

    def test_weekly_monday_triggers_hard(self):
        notices, skips = rule_01_closure(make_day(date=MONDAY), self._weekly_poi(), NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["rule_id"], "rule_01_closure")
        self.assertEqual(notices[0]["severity"], "hard")
        self.assertEqual(notices[0]["outcome"], "pending")
        self.assertEqual(notices[0]["channel"], "modal_confirm")
        self.assertEqual(notices[0]["message_key"], "rule.closure.confirm")
        self.assertEqual(notices[0]["message_args"]["weekday"], "Monday")
        self.assertEqual(skips, [])

    def test_weekly_tuesday_does_not_trigger(self):
        notices, _ = rule_01_closure(make_day(date=TUESDAY), self._weekly_poi(), NOW)
        self.assertEqual(notices, [])

    def test_holiday_exception_open_does_not_trigger(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [
                {"kind": "weekly", "weekday": 1},
                {"kind": "holiday_exception_open", "date_from": "2026-10-05", "date_to": "2026-10-05"},
            ],
            "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(date="2026-10-05"), poi, NOW)
        self.assertEqual(notices, [])

    def test_holiday_exception_closed_triggers(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "holiday_exception_closed",
                               "date_from": "2026-02-15", "date_to": "2026-02-21",
                               "reason_zh": "春节假期闭馆", "reason_en": "Spring Festival closure"}],
            "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(date="2026-02-18"), poi, NOW)
        self.assertEqual([n["severity"] for n in notices], ["hard"])
        self.assertEqual(notices[0]["message_key"], "rule.closure.reason")
        self.assertEqual(notices[0]["message_args"]["reason"], "Spring Festival closure")
        self.assertNotIn("weekday", notices[0]["message_args"])

    def test_special_period_triggers(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "special_period",
                               "date_from": "2026-02-15", "date_to": "2026-02-21",
                               "reason_zh": "春节假期闭馆", "reason_en": "Spring Festival closure"}],
            "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(date="2026-02-18"), poi, NOW)
        self.assertEqual([n["severity"] for n in notices], ["hard"])
        self.assertEqual(notices[0]["message_key"], "rule.closure.reason")
        self.assertEqual(notices[0]["message_args"]["reason"], "Spring Festival closure")

    def test_maintenance_triggers(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "maintenance",
                               "date_from": "2026-11-01", "date_to": "2026-11-03",
                               "reason_zh": "设备修缮", "reason_en": "Maintenance work"}],
            "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(date="2026-11-02"), poi, NOW)
        self.assertEqual([n["severity"] for n in notices], ["hard"])
        self.assertEqual(notices[0]["message_key"], "rule.closure.reason")
        self.assertEqual(notices[0]["message_args"]["reason"], "Maintenance work")

    def test_unknown_status_soft_hint(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "unknown",
            "closure_rules": [], "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(), poi, NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["severity"], "soft_hint")
        self.assertEqual(notices[0]["message_key"], "rule.closure.data_unknown")

    def test_unverified_status_soft_hint(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "unverified",
            "closure_rules": [], "is_enclosed_attraction": True})
        notices, _ = rule_01_closure(make_day(), poi, NOW)
        self.assertEqual(notices[0]["message_key"], "rule.closure.data_unverified")
        self.assertEqual(notices[0]["severity"], "soft_hint")

    def test_not_enclosed_no_trigger(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}],
            "is_enclosed_attraction": False})
        notices, _ = rule_01_closure(make_day(date=MONDAY), poi, NOW)
        self.assertEqual(notices, [])

    def test_missing_enclosed_soft_hint(self):
        poi = make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}]})
        notices, _ = rule_01_closure(make_day(date=MONDAY), poi, NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["severity"], "soft_hint")
        self.assertEqual(notices[0]["message_key"], "rule.closure.data_unknown")


class Rule02Tests(unittest.TestCase):
    def _lightup_poi(self, required=True, windows=None, t_light_rule="window_start_minus_30"):
        return make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified", "closure_rules": [],
            "is_enclosed_attraction": False,
            "light_up": {"required": required, "T_light_rule": t_light_rule,
                         "windows": windows if windows is not None else [
                             {"date_from": "05-01", "date_to": "09-30",
                              "start": "19:00", "close": "23:00"}]}})

    def test_too_early(self):
        notices, skips = rule_02_lightup(make_day(date="2026-07-10"),
                                         self._lightup_poi(), "17:40", NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message_key"], "rule.lightup.too_early")
        self.assertEqual(notices[0]["message_args"]["T_light"], "18:30")
        self.assertEqual(skips, [])

    def test_at_t_light_no_trigger(self):
        notices, _ = rule_02_lightup(make_day(date="2026-07-10"),
                                     self._lightup_poi(), "18:30", NOW)
        self.assertEqual(notices, [])

    def test_too_late(self):
        notices, _ = rule_02_lightup(make_day(date="2026-07-10"),
                                     self._lightup_poi(), "23:30", NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message_key"], "rule.lightup.too_late")

    def test_no_matching_window(self):
        notices, skips = rule_02_lightup(make_day(date="2026-10-12"),
                                         self._lightup_poi(), "17:40", NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_02_lightup", "no_match"), skips)

    def test_empty_windows_skips(self):
        notices, skips = rule_02_lightup(make_day(), self._lightup_poi(windows=[]),
                                         "17:40", NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_02_lightup", "missing_data"), skips)

    def test_sunset_missing_skips(self):
        notices, skips = rule_02_lightup(make_day(date="2026-07-10"),
                                         self._lightup_poi(t_light_rule="sunset"),
                                         "17:40", NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_02_lightup", "missing_data"), skips)

    def test_not_required_no_trigger(self):
        notices, skips = rule_02_lightup(make_day(), self._lightup_poi(required=False),
                                         "17:40", NOW)
        self.assertEqual(notices, [])
        self.assertEqual(skips, [])


class Rule03Tests(unittest.TestCase):
    RULES, MAPPINGS = None, None

    @classmethod
    def setUpClass(cls):
        cls.RULES, cls.MAPPINGS = load_contracts(ROOT)

    def _spread_poi(self, poi_id, lat, lng, core=True):
        return make_poi(poi_id=poi_id, coordinate={"lat": lat, "lng": lng, "crs": "WGS84"},
                        city={"is_core_urban": core})

    def test_far_and_slow_triggers(self):
        p1 = self._spread_poi("sh_poi_00101", 31.23, 121.47)
        p2 = self._spread_poi("sh_poi_00102", 31.53, 121.47)
        distance = haversine_km(31.23, 121.47, 31.53, 121.47)
        self.assertGreater(distance, 25)
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 70 * 60})]
        lookup = {"sh_poi_00101": p1, "sh_poi_00102": p2}
        notices, skips = rule_03_spread(make_day(), stops, lookup, self.RULES, NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message_key"], "rule.spread.long_transit")
        self.assertEqual(notices[0]["message_args"]["duration_minutes"], 70)
        self.assertAlmostEqual(notices[0]["message_args"]["distance_km"],
                               round(distance, 1), places=1)

    def test_far_but_fast_no_trigger(self):
        p1 = self._spread_poi("sh_poi_00101", 31.23, 121.47)
        p2 = self._spread_poi("sh_poi_00102", 31.53, 121.47)
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 25 * 60})]
        notices, _ = rule_03_spread(make_day(), stops,
                                    {"sh_poi_00101": p1, "sh_poi_00102": p2},
                                    self.RULES, NOW)
        self.assertEqual(notices, [])

    def test_near_and_slow_no_trigger(self):
        p1 = self._spread_poi("sh_poi_00101", 31.230, 121.470)
        p2 = self._spread_poi("sh_poi_00102", 31.231, 121.470)
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 35 * 60})]
        notices, _ = rule_03_spread(make_day(), stops,
                                    {"sh_poi_00101": p1, "sh_poi_00102": p2},
                                    self.RULES, NOW)
        self.assertEqual(notices, [])

    def test_suburb_no_trigger(self):
        p1 = self._spread_poi("sh_poi_00101", 31.23, 121.47, core=True)
        p2 = self._spread_poi("sh_poi_00102", 31.53, 121.47, core=False)
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 70 * 60})]
        notices, skips = rule_03_spread(make_day(), stops,
                                        {"sh_poi_00101": p1, "sh_poi_00102": p2},
                                        self.RULES, NOW)
        self.assertEqual(notices, [])
        self.assertEqual(skips, [])

    def test_missing_city_config_skips(self):
        rules = {"rules": [{"rule_id": "rule_03_spread", "city_config": {}}]}
        p1 = self._spread_poi("sh_poi_00101", 31.23, 121.47)
        p2 = self._spread_poi("sh_poi_00102", 31.53, 121.47)
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 70 * 60})]
        notices, skips = rule_03_spread(make_day(), stops,
                                        {"sh_poi_00101": p1, "sh_poi_00102": p2},
                                        rules, NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_03_spread", "missing_data"), skips)

    def test_missing_core_skips(self):
        p1 = self._spread_poi("sh_poi_00101", 31.23, 121.47)
        p2 = make_poi(poi_id="sh_poi_00102", coordinate={"lat": 31.53, "lng": 121.47, "crs": "WGS84"})
        stops = [make_stop("sh_poi_00101"),
                 make_stop("sh_poi_00102", transit={"duration_seconds": 70 * 60})]
        notices, skips = rule_03_spread(make_day(), stops,
                                        {"sh_poi_00101": p1, "sh_poi_00102": p2},
                                        self.RULES, NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_03_spread", "missing_data"), skips)


class Rule04Tests(unittest.TestCase):
    RULES, MAPPINGS = None, None

    @classmethod
    def setUpClass(cls):
        cls.RULES, cls.MAPPINGS = load_contracts(ROOT)

    def _garden(self, poi_id):
        return make_poi(poi_id=poi_id, level2="classical_garden")

    def test_three_same_triggers(self):
        stops = [make_stop("sh_poi_00101", order=1), make_stop("sh_poi_00102", order=2),
                 make_stop("sh_poi_00103", order=3)]
        lookup = {stop["poi_id"]: self._garden(stop["poi_id"]) for stop in stops}
        notices, _ = rule_04_homogeneous(make_day(), stops, lookup, self.RULES, self.MAPPINGS, NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message_key"], "rule.homogeneous.banner")
        self.assertEqual(notices[0]["message_args"]["count"], 3)

    def test_count_updates_not_hardcoded(self):
        stops = [make_stop(f"sh_poi_0010{i}", order=i) for i in range(1, 6)]
        lookup = {stop["poi_id"]: self._garden(stop["poi_id"]) for stop in stops}
        notices, _ = rule_04_homogeneous(make_day(), stops, lookup, self.RULES, self.MAPPINGS, NOW)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message_args"]["count"], 5)

    def test_different_level2_no_trigger(self):
        stops = [make_stop("sh_poi_00101", order=1), make_stop("sh_poi_00102", order=2),
                 make_stop("sh_poi_00103", order=3)]
        lookup = {
            "sh_poi_00101": make_poi(poi_id="sh_poi_00101", level2="classical_garden"),
            "sh_poi_00102": make_poi(poi_id="sh_poi_00102", level2="museum"),
            "sh_poi_00103": make_poi(poi_id="sh_poi_00103", level2="park"),
        }
        notices, _ = rule_04_homogeneous(make_day(), stops, lookup, self.RULES, self.MAPPINGS, NOW)
        self.assertEqual(notices, [])

    def test_unknown_level2_skipped_without_error(self):
        stops = [make_stop("sh_poi_00101", order=1), make_stop("sh_poi_00102", order=2),
                 make_stop("sh_poi_00103", order=3)]
        lookup = {stop["poi_id"]: make_poi(poi_id=stop["poi_id"], level2="not_in_taxonomy")
                  for stop in stops}
        notices, skips = rule_04_homogeneous(make_day(), stops, lookup, self.RULES, self.MAPPINGS, NOW)
        self.assertEqual(notices, [])
        self.assertEqual(skips, [])

    def test_missing_threshold_skips(self):
        rules = {"rules": [{"rule_id": "rule_04_homogeneous", "trigger": {}}]}
        stops = [make_stop("sh_poi_00101", order=1), make_stop("sh_poi_00102", order=2),
                 make_stop("sh_poi_00103", order=3)]
        lookup = {stop["poi_id"]: self._garden(stop["poi_id"]) for stop in stops}
        notices, skips = rule_04_homogeneous(make_day(), stops, lookup,
                                             rules, self.MAPPINGS, NOW)
        self.assertEqual(notices, [])
        self.assertIn(("rule_04_homogeneous", "missing_data"), skips)

    def test_same_day_scope(self):
        two = [make_stop("sh_poi_00101", order=1), make_stop("sh_poi_00102", order=2)]
        lookup = {stop["poi_id"]: self._garden(stop["poi_id"]) for stop in two}
        notices, _ = rule_04_homogeneous(make_day(), two, lookup, self.RULES, self.MAPPINGS, NOW)
        self.assertEqual(notices, [])


class TimelineTests(unittest.TestCase):
    def test_timeline_matches_fixture(self):
        payload = json.loads((ROOT / "contracts" / "examples" / "trip_shanghai_2d.json")
                             .read_text(encoding="utf-8"))
        day2 = next(day for day in payload["days"] if day["day_index"] == 2)
        timeline = build_timeline(payload, day2)
        for stop, computed in zip(day2["ordered_stops"], timeline):
            if stop.get("arrival_at") is not None:
                self.assertEqual(computed["arrival_at"], stop["arrival_at"])
            if stop.get("departure_at") is not None:
                self.assertEqual(computed["departure_at"], stop["departure_at"])
            self.assertEqual(computed["departure_at"] - computed["arrival_at"],
                             stop["planned_dwell_minutes"] * 60)

    def test_day1_cross_midnight_arrival_only(self):
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY,
                                        stops=[{"stop_order": 1, "stop_type": "hotel",
                                                "poi_id": None, "locked": True,
                                                "arrival_at": 1791824400, "departure_at": None,
                                                "user_preferred_arrival_local": None,
                                                "planned_dwell_minutes": 0,
                                                "transit_from_previous": None,
                                                "rule_notices": []}])])
        timeline = build_timeline(trip, trip["days"][0])
        self.assertEqual(timeline[0]["arrival_at"], 1791824400)
        self.assertEqual(timeline[0]["arrival_local"], "01:00")

    def test_timeline_idempotent(self):
        payload = json.loads((ROOT / "contracts" / "examples" / "trip_shanghai_2d.json")
                             .read_text(encoding="utf-8"))
        day2 = next(day for day in payload["days"] if day["day_index"] == 2)
        first = build_timeline(payload, day2)
        second = build_timeline(payload, day2)
        self.assertEqual(first, second)

    def test_transfer_overhead_counts_into_timeline(self):
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY, stops=[
            make_stop("sh_poi_00101", order=1, transit=None),
            make_stop("sh_poi_00102", order=2, dwell=60, transit={
                "duration_seconds": 2700, "walking_duration_seconds": 760,
                "transfer_overhead": {"applies_to": "walking_segment",
                                      "factor": 1.3, "counts_in_timeline": True}}),
        ])])
        timeline = build_timeline(trip, trip["days"][0])
        self.assertEqual(timeline[1]["arrival_at"],
                         timeline[0]["departure_at"] + 2700 + int(760 * 0.3))

    def test_transfer_overhead_not_counted_when_false(self):
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY, stops=[
            make_stop("sh_poi_00101", order=1, transit=None),
            make_stop("sh_poi_00102", order=2, dwell=60, transit={
                "duration_seconds": 2700, "walking_duration_seconds": 760,
                "transfer_overhead": {"applies_to": "walking_segment",
                                      "factor": 1.3, "counts_in_timeline": False}}),
        ])])
        timeline = build_timeline(trip, trip["days"][0])
        self.assertEqual(timeline[1]["arrival_at"],
                         timeline[0]["departure_at"] + 2700)


class ExecutionModelTests(unittest.TestCase):
    def test_soft_reminders_keep_day_poi_and_time_context(self):
        trip=make_trip(days=[make_day(day_index=2,date=TUESDAY,stops=[make_stop('night',transit={'duration_seconds':600})])])
        poi=make_poi(poi_id='night',operating={'closure_data_status':'unverified',
            'light_up':{'required':True,'windows':[{'date_from':'01-01','date_to':'12-31','start':'19:00','close':'23:00'}]}})
        poi['names']={'zh-Hans':'东方明珠','en':'Oriental Pearl Tower'}
        result=evaluate_day(trip,trip['days'][0],{'night':poi},self.RULES,self.MAPPINGS,NOW)
        light=next(n for n in result['notices'] if n['message_key']=='rule.lightup.too_early')
        for notice in result['notices']:
            self.assertEqual(notice['message_args']['day_index'],2)
        self.assertEqual(light['message_args']['poi_id'],'night')
        self.assertEqual(light['message_args']['poi_name_zh'],'东方明珠')
        self.assertTrue(light['message_args']['arrival_local'])
        self.assertEqual(light['message_args']['light_start'],'19:00')
        self.assertEqual(light['message_args']['T_light'],'18:30')

    RULES, MAPPINGS = None, None

    @classmethod
    def setUpClass(cls):
        cls.RULES, cls.MAPPINGS = load_contracts(ROOT)

    def test_evaluate_does_not_mutate_stops(self):
        """方案 A 核心护栏：求值前后 ordered_stops 深比较完全一致。"""
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY,
                                        stops=[make_stop("sh_poi_00088", order=1)])])
        lookup = {"sh_poi_00088": make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}],
            "is_enclosed_attraction": True})}
        before = json.dumps(trip["days"], sort_keys=True)
        evaluate_day(trip, trip["days"][0], lookup, self.RULES, self.MAPPINGS, NOW)
        after = json.dumps(trip["days"], sort_keys=True)
        self.assertEqual(before, after)

    def test_severity_sort(self):
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY,
                                        stops=[make_stop("sh_poi_00088", order=1)])])
        lookup = {"sh_poi_00088": make_poi(operating={
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}],
            "is_enclosed_attraction": True,
            "light_up": {"required": True, "windows": [
                {"date_from": "01-01", "date_to": "12-31", "start": "19:00", "close": "23:00"}]}})}
        result = evaluate_day(trip, trip["days"][0], lookup, self.RULES, self.MAPPINGS, NOW)
        severities = [notice["severity"] for notice in result["notices"]]
        self.assertEqual(severities, sorted(severities, key=lambda s: rules.SEVERITY_ORDER[s]))
        self.assertEqual(result["evaluated_rules"], RULE_IDS)

    def test_render_capacity_overflow(self):
        notices = [{"channel": "toast", "severity": "soft_hint"} for _ in range(5)]
        rendered, overflow = summarize_render(notices)
        self.assertEqual(len(rendered), 3)
        self.assertEqual(overflow, 2)

    def test_missing_data_visible_in_skipped_rules(self):
        """离线/缺耗时数据时不得静默当作通过。"""
        trip = make_trip(days=[make_day(day_index=1, date=MONDAY,
                                        stops=[make_stop("sh_poi_00101", order=1),
                                               make_stop("sh_poi_00102", order=2,
                                                         transit=None)])])
        lookup = {
            "sh_poi_00101": make_poi(poi_id="sh_poi_00101", city={"is_core_urban": True}),
            "sh_poi_00102": make_poi(poi_id="sh_poi_00102", city={"is_core_urban": True}),
        }
        result = evaluate_day(trip, trip["days"][0], lookup, self.RULES, self.MAPPINGS, NOW)
        reasons = {(item["rule_id"], item["reason"]) for item in result["skipped_rules"]}
        self.assertIn(("rule_03_spread", "missing_data"), reasons)


if __name__ == "__main__":
    unittest.main()
