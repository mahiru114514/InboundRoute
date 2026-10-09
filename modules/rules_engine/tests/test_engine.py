"""rules_engine HTTP 服务单测：用假 trip_engine 上游验证健康/鉴权/求值/确认/降级。"""
from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]        # workspace root
MODULE = Path(__file__).resolve().parents[1]      # modules/rules_engine
for candidate in (str(ROOT), str(MODULE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from client import TripEngineClient  # noqa: E402
from engine import RulesService, build_server, MODULE_ID  # noqa: E402

TOKEN = "rules-token-1234567890"
NOW = 1791819600
MONDAY = "2026-10-12"
MUSEUM = "sh_poi_00088"
# 预检用例需要一个「还没进任何一天、但周一闭馆」的点，否则只能测到重复校验。
BUND = "sh_poi_00042"


def museum_poi():
    return {
        "poi_id": MUSEUM, "names": {"zh-Hans": "上海博物馆", "en": "Shanghai Museum"},
        "category": {"level1": "history_culture", "level2": "museum",
                     "label_en": "Museum", "label_zh": "博物馆"},
        "coordinate": {"lat": 31.230025, "lng": 121.469804, "crs": "WGS84"},
        "operating_rules": {
            "opening_hours": [], "closure_data_status": "verified",
            "closure_rules": [{"kind": "weekly", "weekday": 1}],
            "is_enclosed_attraction": True},
        "provenance": {"source": "manual", "updated_at": 0},
    }


def bund_poi():
    """周一闭馆，且当前不在行程里 —— 用来验证「加入之前的预检」。"""
    poi = museum_poi()
    poi.update({"poi_id": BUND, "names": {"zh-Hans": "外滩", "en": "The Bund"},
                "category": {"level1": "modern_skyline", "level2": "waterfront",
                             "label_en": "Waterfront", "label_zh": "滨江"}})
    return poi


def sample_trip():
    return {
        "trip_id": "trip_engine1", "version": 1, "status": "draft", "timezone": "Asia/Shanghai",
        "user_profile": {"party_composition": "solo", "pacing": "balanced", "interests": []},
        "anchor_arrival": {"arrival_at": 1791819000, "activity_start_at": 1791824400,
                           "border_buffer_minutes": 90, "location_name": "PVG",
                           "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"}},
        "anchor_hotel": {"name_en": "Hotel", "name_zh": "酒店",
                         "coordinate": {"lat": 31.2335, "lng": 121.4789, "crs": "WGS84"}},
        "days": [{
            "day_index": 1, "date": MONDAY, "day_status": "partial",
            "daily_start_local": "09:00", "poi_cap": 6,
            "ordered_stops": [{
                "stop_order": 1, "stop_type": "poi", "poi_id": MUSEUM, "locked": False,
                "arrival_at": None, "departure_at": None, "user_preferred_arrival_local": None,
                "planned_dwell_minutes": 90, "transit_from_previous": None, "rule_notices": []}],
        }],
        "revision_history": [],
    }


class FakeTripEngineHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def _reply(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            return self._reply(200, {"ok": True, "data": {
                "module_id": "trip_engine", "status": "ok", "ready": True}})
        if path.startswith("/trips/"):
            trip = self.server.trips.get(path.split("/")[2])
            if trip is None:
                return self._reply(404, {"ok": False, "error": {"code": "TRIP_NOT_FOUND", "message": "x"}})
            return self._reply(200, {"ok": True, "data": trip})
        if path.startswith("/pois/"):
            poi = self.server.pois.get(path.split("/")[2])
            if poi is None:
                return self._reply(404, {"ok": False, "error": {"code": "POI_NOT_FOUND", "message": "x"}})
            return self._reply(200, {"ok": True, "data": poi})
        return self._reply(404, {"ok": False, "error": {"code": "BAD_REQUEST", "message": "x"}})

    def do_PATCH(self):
        payload = self._body()
        trip = self.server.trips[urllib.parse.urlsplit(self.path).path.split("/")[2]]
        for day_patch in payload.get("days", []):
            day = next(d for d in trip["days"] if d["day_index"] == day_patch["day_index"])
            for stop_patch in day_patch.get("ordered_stops", []):
                stop = next(s for s in day["ordered_stops"]
                            if s["stop_order"] == stop_patch["stop_order"])
                if "rule_notices" in stop_patch:
                    stop["rule_notices"] = stop_patch["rule_notices"]
        trip["version"] += 1
        trip["revision_history"].append({"version": trip["version"], "changed_at": NOW,
                                         "operation": "confirm_conflict", "target": MUSEUM})
        return self._reply(200, {"ok": True, "data": trip})


def build_fake_engine():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTripEngineHandler)
    server.daemon_threads = True
    server.trips = {"trip_engine1": sample_trip()}
    server.pois = {MUSEUM: museum_poi(), BUND: bund_poi()}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class EngineHttpTests(unittest.TestCase):
    def setUp(self):
        self.fake = build_fake_engine()
        client = TripEngineClient(f"http://127.0.0.1:{self.fake.server_port}", "upstream-token")
        service = RulesService(ROOT, client=client, wall_clock=lambda: NOW)
        self.server = build_server(service, TOKEN, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.fake.shutdown()
        self.fake.server_close()

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

    # ------------------------------------------------------------ 健康与鉴权

    def test_health_is_open(self):
        status, envelope = self.call("GET", "/health", token=None)
        self.assertEqual(status, 200)
        data = envelope["data"]
        self.assertEqual(data["module_id"], MODULE_ID)
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["ready"])
        self.assertFalse(data["degraded"])

    def test_other_endpoints_require_token(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:evaluate", token=None)
        self.assertEqual(status, 403)
        self.assertEqual(envelope["error"]["code"], "FORBIDDEN")
        status, _ = self.call("POST", "/trips/trip_engine1/rules:evaluate", token="wrong")
        self.assertEqual(status, 403)

    def test_host_header_is_checked(self):
        status, _ = self.call("POST", "/trips/trip_engine1/rules:evaluate",
                              headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    # ------------------------------------------------------------ 求值

    def test_evaluate_returns_hard_conflict(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:evaluate",
                                     {"trigger": "add_stop"})
        self.assertEqual(status, 200)
        data = envelope["data"]
        self.assertIn("notices", data)
        self.assertIn("skipped_rules", data)
        self.assertEqual(data["evaluated_rules"], [
            "rule_01_closure", "rule_02_lightup", "rule_03_spread", "rule_04_homogeneous"])
        self.assertEqual(data["overflow"], 0)
        hard = [n for n in data["notices"] if n["severity"] == "hard"]
        self.assertEqual(len(hard), 1)
        self.assertEqual(hard[0]["message_key"], "rule.closure.confirm")
        self.assertIn("notice_id", hard[0]["message_args"])

    def test_evaluate_bad_trigger(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:evaluate",
                                     {"trigger": "nope"})
        self.assertEqual(status, 400)
        self.assertEqual(envelope["error"]["code"], "BAD_REQUEST")

    # ------------------------------------------------------------ 冲突确认

    def test_confirm_proceed_anyway(self):
        status, envelope = self.call(
            "POST", "/trips/trip_engine1/conflicts/rule_01_closure:1:sh_poi_00088/confirm",
            {"decision": "proceed_anyway"})
        self.assertEqual(status, 200, envelope)
        notice = envelope["data"]["notice"]
        self.assertEqual(notice["outcome"], "confirmed_proceed")
        self.assertEqual(notice["confirmed_at"], NOW)
        persisted = envelope["data"]["trip"]["days"][0]["ordered_stops"][0]["rule_notices"]
        self.assertEqual(persisted[0]["outcome"], "confirmed_proceed")

    def test_confirm_replay_is_idempotent(self):
        path = "/trips/trip_engine1/conflicts/rule_01_closure:1:sh_poi_00088/confirm"
        status, first = self.call("POST", path, {"decision": "proceed_anyway"})
        self.assertEqual(status, 200)
        status, second = self.call("POST", path, {"decision": "proceed_anyway"})
        self.assertEqual(status, 200)
        self.assertEqual(first["data"]["trip"]["version"], 2)
        self.assertEqual(second["data"]["trip"]["version"], 2)
        self.assertEqual(len(second["data"]["trip"]["revision_history"]), 1)

    def test_confirm_reject(self):
        status, envelope = self.call(
            "POST", "/trips/trip_engine1/conflicts/rule_01_closure:1:sh_poi_00088/confirm",
            {"decision": "reject"})
        self.assertEqual(status, 200, envelope)
        self.assertEqual(envelope["data"]["notice"]["outcome"], "rejected")

    def test_confirm_bad_decision(self):
        status, envelope = self.call(
            "POST", "/trips/trip_engine1/conflicts/rule_01_closure:1:sh_poi_00088/confirm",
            {"decision": "maybe"})
        self.assertEqual(status, 400)

    def test_unknown_route(self):
        status, envelope = self.call("GET", "/nope")
        self.assertEqual(status, 404)


class PrecheckTests(EngineHttpTests):
    """POST /trips/{id}/rules:precheck —— 加入景点之前先看硬冲突，且绝不落盘。"""

    def test_precheck_reports_hard_conflict_without_persisting(self):
        before = json.loads(json.dumps(self.fake.trips["trip_engine1"]))
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"day_index": 1, "poi_id": BUND})
        self.assertEqual(status, 200, envelope)
        data = envelope["data"]
        self.assertTrue(data["would_block"], data)
        self.assertEqual(data["poi_id"], BUND)
        self.assertEqual(data["day_index"], 1)
        self.assertTrue(data["hard_conflicts"], data)
        self.assertTrue(all(n["severity"] == "hard" for n in data["hard_conflicts"]))
        # 关键：预检不能改动行程（版本与内容都不许变）
        self.assertEqual(self.fake.trips["trip_engine1"], before)
        self.assertEqual(self.fake.trips["trip_engine1"]["version"], before["version"])

    def test_precheck_rejects_poi_already_in_that_day(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"day_index": 1, "poi_id": MUSEUM})
        self.assertEqual(status, 400, envelope)
        self.assertIn("已经在 Day 1 里", envelope["error"]["message"])

    def test_precheck_requires_day_and_poi(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"poi_id": BUND})
        self.assertEqual(status, 400, envelope)
        self.assertIn("day_index", envelope["error"]["message"])
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"day_index": 1})
        self.assertEqual(status, 400, envelope)
        self.assertIn("poi_id", envelope["error"]["message"])

    def test_precheck_rejects_unknown_day_and_unknown_poi(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"day_index": 9, "poi_id": BUND})
        self.assertEqual(status, 404, envelope)
        self.assertIn("Day 9", envelope["error"]["message"])

    def test_precheck_requires_token(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:precheck",
                                     {"day_index": 1, "poi_id": BUND}, token=None)
        self.assertEqual(status, 403, envelope)


class OverflowTests(EngineHttpTests):
    """被 channel 承载位裁掉的建议必须回传，不能被「还有 N 条建议」吞掉。"""

    def test_evaluate_returns_overflow_notices(self):
        status, envelope = self.call("POST", "/trips/trip_engine1/rules:evaluate",
                                     {"trigger": "load_trip"})
        self.assertEqual(status, 200, envelope)
        data = envelope["data"]
        # 无论有没有溢出，字段都要在，前端才能统一处理「展开全部」。
        self.assertIn("overflow_notices", data)
        self.assertIsInstance(data["overflow_notices"], list)
        self.assertEqual(data["overflow"], len(data["overflow_notices"]))


class DegradedTests(unittest.TestCase):
    def test_upstream_down_degrades_health_and_business(self):
        service = RulesService(ROOT, client=None, wall_clock=lambda: NOW)
        server = build_server(service, TOKEN, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        try:
            client.request("GET", "/health")
            response = client.getresponse()
            envelope = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(envelope["data"]["status"], "degraded")
            self.assertEqual(envelope["data"]["degraded_reason"], "upstream_down")

            client.request("POST", "/trips/trip_engine1/rules:evaluate",
                           body=json.dumps({}).encode("utf-8"),
                           headers={"X-Module-Token": TOKEN, "Content-Type": "application/json"})
            response = client.getresponse()
            envelope = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 503)
            self.assertEqual(envelope["error"]["code"], "UPSTREAM_TIMEOUT")
        finally:
            client.close()
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
