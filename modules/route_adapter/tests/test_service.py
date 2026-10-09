import common  # noqa: F401
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from contracts.runtime import registry as reg

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROM = {"type": "poi", "poi_id": "sh_poi_00042", "station_id": None, "name_zh": "外滩",
        "name_en": "The Bund", "coordinate": {"lat": 31.2397, "lng": 121.49, "crs": "WGS84"}}
TO = {"type": "poi", "poi_id": "sh_poi_00088", "station_id": None, "name_zh": "上海博物馆",
      "name_en": "Shanghai Museum", "coordinate": {"lat": 31.2304, "lng": 121.4737, "crs": "WGS84"}}


class _NullLogger:
    def info(self, message):
        pass


class FakeTripEngine:
    def __init__(self):
        handler = self._make_handler()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003
                return

            def _send(self, status, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                if self.path == "/health":
                    self._send(200, {"module_id": "trip_engine", "status": "ok", "ready": True,
                                     "started_at": int(time.time()), "degraded": False,
                                     "degraded_reason": None})
                    return
                if self.path.startswith("/trips/"):
                    self._send(200, {"ok": True, "data": {
                        "trip_id": self.path.split("/")[2], "version": 7,
                        "days": [{"day_index": 1, "ordered_stops": []}]}})
                    return
                if self.path.startswith("/pois/"):
                    self._send(200, {"ok": True, "data": {
                        "poi_id": self.path.split("/")[2],
                        "coordinate": {"lat": 31.23, "lng": 121.47, "crs": "WGS84"}}})
                    return
                self._send(404, {"ok": False, "error": {"code": "NOT_FOUND"}})

        return Handler

    def start(self):
        self.thread.start()

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


class ServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="route_adapter_test_")
        self.addCleanup(temporary.cleanup)
        self.tmp = temporary.name
        self.workspace = self.tmp
        os.makedirs(os.path.join(self.workspace, "data"), exist_ok=True)
        self.fake = FakeTripEngine()
        self.addCleanup(self.fake.stop)
        self.fake.start()
        reg.write(reg.build_registration("trip_engine", self.fake.port, "fake-token",
                                         depends_on=[], endpoints=["/health", "/trips"]),
                  self.workspace)

    def _start_service(self, config=None):
        from service import RouteAdapterService
        self.service = RouteAdapterService(
            config or {"provider": "mock"}, os.path.join(self.workspace, "data", "route_adapter"),
            self.workspace, _NullLogger(), MODULE_DIR)
        self.addCleanup(self.service.stop)
        self.service.start()
        self.registration = reg.read(self.workspace, "route_adapter")
        self.base = self.registration.base_url
        self.token = self.registration.token

    def _get(self, path, token=None):
        req = urllib.request.Request(self.base + path)
        if token is not None:
            req.add_header("X-Module-Token", token)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _post(self, path, payload, token=None, idem=None):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=body, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if token is not None:
            req.add_header("X-Module-Token", token)
        if idem is not None:
            req.add_header("Idempotency-Key", idem)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_health_public(self):
        self._start_service()
        status, payload = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["module_id"], "route_adapter")
        self.assertEqual(payload["status"], "ok")

    def test_amap_without_key_is_unready_and_compute_returns_json(self):
        with patch.dict(os.environ, {'AMAP_WEB_KEY': ''}):
            self._start_service({'provider': 'amap', 'providers': {'amap': {'city': '上海'}}})
        status, health = self._get('/health')
        self.assertEqual(status, 200)
        self.assertFalse(health['ready'])
        self.assertEqual(health['status'], 'degraded')
        self.assertEqual(health['degraded_reason'], 'provider_not_configured')
        # Keep the HTTP connection usable on successive configuration failures.
        for _ in range(2):
            status, payload = self._post('/trips/trip_1/days/1/routes:compute',
                {'modes': ['transit'], 'from': FROM, 'to': TO}, token=self.token)
            self.assertEqual(status, 200)
            route = payload['data']['routes'][0]
            self.assertEqual(route['data_source'], 'degraded')
            self.assertEqual(route['degraded_reason'], 'unsupported_city')
            self.assertIsNone(route['duration_seconds'])
            self.assertEqual(common.validate_route(route), [])

    def test_amap_health_does_not_disclose_configured_key(self):
        self._start_service({'provider': 'amap', 'providers': {'amap': {
            'api_key': 'test-secret', 'city': '上海'}}})
        _, health = self._get('/health')
        self.assertTrue(health['ready'])
        self.assertEqual(health['status'], 'ok')
        self.assertNotIn('test-secret', json.dumps(health))

    def test_business_requires_token(self):
        self._start_service()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/stations/sh_stn_00107")
        self.assertEqual(ctx.exception.code, 403)

    def test_registry_format(self):
        self._start_service()
        self.assertEqual(self.registration.module_id, "route_adapter")
        self.assertEqual(self.registration.contract_version, reg.CONTRACT_VERSION)
        self.assertEqual(self.registration.depends_on, ["trip_engine"])
        self.assertTrue(self.registration.token)
        self.assertTrue(self.registration.base_url.startswith("http://127.0.0.1:"))

    def test_compute_routes_and_station(self):
        self._start_service()
        status, payload = self._post("/trips/trip_1/days/1/routes:compute",
                                     {"modes": ["transit", "taxi", "walk"], "from": FROM, "to": TO},
                                     token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["data"]["routes"]), 1)
        self.assertEqual(common.validate_route(payload["data"]["routes"][0]), [])

        status, station = self._get("/stations/sh_stn_00107", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(station["data"]["station_id"], "sh_stn_00107")

    def test_drop_off_endpoint(self):
        self._start_service()
        status, payload = self._get("/pois/sh_poi_00042/drop-off", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["source"], "curated")

    def test_idempotency_replay(self):
        self._start_service()
        _, first = self._post("/trips/trip_1/days/1/routes:compute",
                              {"modes": ["transit"], "from": FROM, "to": TO}, token=self.token, idem="idem-1")
        _, second = self._post("/trips/trip_1/days/1/routes:compute",
                               {"modes": ["transit"], "from": FROM, "to": TO}, token=self.token, idem="idem-1")
        self.assertEqual(first["data"]["routes"][0]["fetched_at"], second["data"]["routes"][0]["fetched_at"])

    def test_upstream_down_degrades(self):
        self._start_service()
        self.fake.stop()
        time.sleep(2.6)
        status, health = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["degraded_reason"], "upstream_down")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/trips/trip_1/days/1/routes:compute",
                       {"modes": ["transit"], "from": FROM, "to": TO}, token=self.token)
        self.assertEqual(ctx.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
