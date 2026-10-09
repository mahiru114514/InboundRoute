import common  # noqa: F401
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from contracts.runtime import registry as reg

_EXAMPLE = os.path.join(common.WORKSPACE, "contracts", "examples", "route_transit_transfer.json")
_STATION = os.path.join(common.WORKSPACE, "modules", "route_adapter", "data", "curated_stations.json")


class _NullLogger:
    def info(self, message):
        pass


class _FakeServer:
    def __init__(self, routes):
        self.routes = routes
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
                for prefix, fn in outer.routes.get("GET", {}).items():
                    if self.path.startswith(prefix):
                        status, payload = fn(self.path)
                        self._send(status, payload)
                        return
                self._send(404, {"ok": False, "error": {"code": "NOT_FOUND"}})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def _trip_payload():
    with open(_EXAMPLE, encoding="utf-8") as fh:
        route = json.load(fh)
    return {
        "trip_id": "trip_1", "version": 7,
        "days": [{"day_index": 1, "date": "2026-10-12", "ordered_stops": [
            {"stop_order": 1, "stop_type": "poi", "poi_id": "sh_poi_00088",
             "arrival_at": 1791819600, "departure_at": 1791825000,
             "name_zh": "上海博物馆", "name_en": "Shanghai Museum",
             "transit_from_previous": route}]}]
    }


def _station_payload(station_id):
    with open(_STATION, encoding="utf-8") as fh:
        stations = json.load(fh)
    for station in stations:
        if station["station_id"] == station_id:
            return station
    return None


class ServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="offline_kit_test_")
        self.addCleanup(temporary.cleanup)
        self.tmp = temporary.name
        os.makedirs(os.path.join(self.tmp, "data"), exist_ok=True)

        def trip_get(path):
            if path == "/health":
                return 200, {"module_id": "trip_engine", "status": "ok", "ready": True,
                             "started_at": int(time.time()), "degraded": False, "degraded_reason": None}
            if path.startswith("/trips/"):
                return 200, {"ok": True, "data": _trip_payload()}
            return 404, {"ok": False, "error": {"code": "NOT_FOUND"}}

        def ra_get(path):
            if path == "/health":
                return 200, {"module_id": "route_adapter", "status": "ok", "ready": True,
                             "started_at": int(time.time()), "degraded": False, "degraded_reason": None}
            if path.startswith("/stations/"):
                station = _station_payload(path.split("/")[-1])
                if station:
                    return 200, {"ok": True, "data": station}
                return 404, {"ok": False, "error": {"code": "NOT_FOUND"}}
            return 404, {"ok": False, "error": {"code": "NOT_FOUND"}}

        self.trip = _FakeServer({"GET": {"/health": trip_get, "/trips/": trip_get}})
        self.route = _FakeServer({"GET": {"/health": ra_get, "/stations/": ra_get}})
        self.addCleanup(self.trip.stop)
        self.trip.start()
        self.addCleanup(self.route.stop)
        self.route.start()
        reg.write(reg.build_registration("trip_engine", self.trip.port, "t", [], ["/health", "/trips"]), self.tmp)
        reg.write(reg.build_registration("route_adapter", self.route.port, "r", [], ["/health", "/stations"]), self.tmp)

    def _start_service(self):
        from service import OfflineKitService
        self.service = OfflineKitService({}, os.path.join(self.tmp, "data", "offline_kit"),
                                         self.tmp, _NullLogger())
        self.addCleanup(self.service.stop)
        self.service.start()
        self.registration = reg.read(self.tmp, "offline_kit")
        self.base = self.registration.base_url
        self.token = self.registration.token

    def _post(self, path, token=None):
        req = urllib.request.Request(self.base + path, data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if token is not None:
            req.add_header("X-Module-Token", token)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _get(self, path, token=None):
        req = urllib.request.Request(self.base + path)
        if token is not None:
            req.add_header("X-Module-Token", token)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_health_public(self):
        self._start_service()
        status, payload = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["module_id"], "offline_kit")
        self.assertEqual(payload["status"], "ok")

    def test_token_required(self):
        self._start_service()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/trips/trip_1/offline-package")
        self.assertEqual(ctx.exception.code, 403)

    def test_generate_offline_package(self):
        self._start_service()
        status, payload = self._post("/trips/trip_1/offline-package", token=self.token)
        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["package_version"], "0.3.0")
        self.assertEqual(data["trip_version"], 7)
        stop = data["payload"]["days"][0]["stops"][0]
        self.assertTrue(stop["stations"])
        self.assertTrue(stop["ask_cards"])

    def test_upstream_down_degrades(self):
        self._start_service()
        self.trip.stop()
        self.route.stop()
        time.sleep(2.6)
        status, health = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "degraded")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/trips/trip_1/offline-package", token=self.token)
        self.assertEqual(ctx.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
