"""web_workbench 集成测试：静态资源、会话令牌、依赖发现、代理转发、降级。

上游用真实的 trip_engine（同一份代码），因此同时覆盖了「工作台 → 引擎」的完整链路。
两个模块的 engine.py 同名，这里用 importlib 分别加载，避免 sys.modules 抢名。
"""
import base64
import http.client
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
TRIP_DIR = ROOT / "modules" / "trip_engine"
WORKBENCH_DIR = ROOT / "modules" / "web_workbench"
for candidate in (str(ROOT), str(CONTRACTS), str(TRIP_DIR), str(WORKBENCH_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# 加载顺序很重要：两个模块的 engine.py / proxy.py 同名，必须与生产路径（plugin.py 用
# `from engine import ...` / `from proxy import ...`）保持一致，否则同一个文件会被加载成
# 两个模块对象，异常类身份不同 → except 抓不到。
trip_engine = load("trip_engine_engine", TRIP_DIR / "engine.py")
workbench_proxy = load("proxy", WORKBENCH_DIR / "proxy.py")
workbench_engine = load("workbench_engine", WORKBENCH_DIR / "engine.py")

WORKBENCH_TOKEN = "workbench-token"
TRIP_TOKEN = "trip-token"


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        # 会话测试需要稳定的默认底图；屏蔽宿主机可能配置的地图环境变量。
        self._saved_map_env = {
            key: os.environ.get(key)
            for key in ("AMAP_JS_KEY", "AMAP_SECURITY_CODE", "MAP_PROVIDER")
        }
        for key in self._saved_map_env:
            os.environ.pop(key, None)

        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data" / "_registry").mkdir(parents=True)
        self.workspace = self.root

        # 上游：真实的 trip_engine
        self.trip_service = trip_engine.TripService(self.root / "data" / "trip_engine")
        self.trip_server = trip_engine.build_server(self.trip_service, TRIP_TOKEN, 0)
        threading.Thread(target=self.trip_server.serve_forever, daemon=True).start()
        self.write_registry("trip_engine", self.trip_server.server_port, TRIP_TOKEN)

        self.services = workbench_proxy.ServiceRegistry(self.root)
        self.server = workbench_engine.build_server(
            self.services, WORKBENCH_TOKEN, 0,
            maps=workbench_engine.map_config({}),
        )
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)

    def tearDown(self):
        for key, value in getattr(self, "_saved_map_env", {}).items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.trip_server.shutdown()
        self.trip_server.server_close()
        self.temp.cleanup()

    def write_registry(self, module_id, port, token):
        from contracts.runtime.registry import CONTRACT_VERSION
        payload = {"module_id": module_id, "port": port, "base_url": f"http://127.0.0.1:{port}",
                   "token": token, "pid": 1, "contract_version": CONTRACT_VERSION, "started_at": 0,
                   "depends_on": [], "endpoints": ["/health"]}
        (self.root / "data" / "_registry" / f"{module_id}.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def call(self, method, path, body=None, token=WORKBENCH_TOKEN, raw=None):
        payload = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        headers = {}
        if token:
            headers["X-Workbench-Token"] = token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        self.client.request(method, path, body=payload, headers=headers)
        response = self.client.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type") or ""
        parsed = json.loads(data.decode("utf-8")) if content_type.startswith("application/json") else None
        return response.status, parsed, data, dict(response.getheaders())

    def raw_call(self, method, path, body=None, token=WORKBENCH_TOKEN):
        """不解析响应体，用于检查 Content-Type 与原始内容。"""
        payload = None if body is None else json.dumps(body).encode()
        headers = {}
        if token:
            headers["X-Workbench-Token"] = token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        self.client.request(method, path, body=payload, headers=headers)
        response = self.client.getresponse()
        data = response.read()
        return response.status, data, response.getheader("Content-Type") or ""

    # ------------------------------------------------------------ 静态资源与会话

    def test_serves_frontend_without_token(self):
        status, _, body, headers = self.call("GET", "/", token=None)
        self.assertEqual(status, 200)
        page = body.decode("utf-8")
        self.assertIn("行程工作台", page)
        self.assertIn("script-src 'self'", headers.get("Content-Security-Policy", ""))

        # 页面引用的每个静态资源都必须真的取得到。漏挂 ASSETS 的表现是浏览器白屏，
        # 而只看引擎接口的测试完全发现不了——上一版就是把 flow.js 写好了却没挂进页面。
        referenced = re.findall(r'(?:src|href)="(/[\w.]+)(?:\?v=(\d+))?"', page)
        urls = [url for url, _ in referenced]
        self.assertIn("/flow.js", urls)
        self.assertIn("/offline_cache.js", urls)
        # 缓存开关必须全页统一，否则会出现新旧文件混用
        self.assertEqual(len({version for _, version in referenced if version}), 1, referenced)
        for asset in urls:
            status, data, content_type = self.raw_call("GET", asset, token=None)
            self.assertEqual(status, 200, asset)
            self.assertGreater(len(data), 200, asset)
            self.assertIn("charset=utf-8", content_type, asset)
        # flow.js 必须先于 app.js：app.js 的 boot() 会调用 initFlow() 恢复历史行程
        self.assertLess(urls.index("/flow.js"), urls.index("/app.js"), urls)

    def test_csp_stays_strict_when_no_provider(self):
        maps = workbench_engine.map_config({"map_provider": "none"})
        self.assertFalse(maps["ready"])
        csp = workbench_engine.build_csp(maps)
        self.assertNotIn("amap.com", csp)                 # 不用底图时不放行任何外部域名
        self.assertNotIn("unpkg.com", csp)
        self.assertIn("script-src 'self'", csp)

    def test_session_exposes_map_config(self):
        status, envelope, _, _ = self.call("GET", "/api/session", token=None)
        self.assertEqual(status, 200)
        maps = envelope["data"]["map"]
        # 未配 key 时默认走免费的 Leaflet 方案
        self.assertEqual(maps["provider"], "leaflet")
        self.assertTrue(maps["ready"])
        self.assertIn("Leaflet", maps["hint"])
        self.assertIn("unpkg.com", maps["leaflet_js"])

    def test_amap_config_relaxes_csp_for_amap_only(self):
        """配了 key 就走高德：CSP 只放行高德域名，安全密钥随会话下发（官方'明文方式'）。"""
        maps = workbench_engine.map_config({"amap_js_key": "demo-key", "amap_security_code": "demo-secret"})
        self.assertEqual(maps["provider"], "amap")
        self.assertTrue(maps["ready"])
        csp = workbench_engine.build_csp(maps)
        self.assertIn("https://webapi.amap.com", csp)
        self.assertIn("https://restapi.amap.com", csp)
        self.assertNotIn("unpkg.com", csp)               # 走这条路时不需要 Leaflet 的 CDN

        server = workbench_engine.build_server(self.services, "k", 0, maps=maps)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        try:
            client.request("GET", "/api/session")
            response = client.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["data"]["map"]["key"], "demo-key")
            self.assertEqual(payload["data"]["map"]["security_mode"], "plain")
        finally:
            client.close()
            server.shutdown()
            server.server_close()

    def test_leaflet_csp_allows_cdn_and_tiles_only(self):
        maps = workbench_engine.map_config({"map_provider": "leaflet"})
        csp = workbench_engine.build_csp(maps)
        self.assertIn("https://unpkg.com", csp)
        self.assertIn("https://cdnjs.cloudflare.com", csp)   # 备用 CDN 也要放行，否则回退无效
        self.assertIn("*.amap.com", csp)                      # 瓦片来自高德公共瓦片
        self.assertIn("connect-src 'self'", csp)
        self.assertNotIn("restapi.amap.com", csp)             # 不需要高德服务 API

    def test_leaflet_has_multiple_cdn_fallbacks(self):
        maps = workbench_engine.map_config({"map_provider": "leaflet"})
        names = [item["name"] for item in maps["leaflet_cdns"]]
        self.assertEqual(names[0], "unpkg")
        self.assertIn("cdnjs", names)                         # 单个 CDN 抖动时仍能加载
        self.assertEqual(maps["leaflet_js"], maps["leaflet_cdns"][0]["js"])
        self.assertTrue(all(item["js"].startswith("https://") for item in maps["leaflet_cdns"]))

    def test_leaflet_has_tile_fallback_for_wgs84(self):
        """高德瓦片（GCJ-02）备一个 WGS84 备用源，前端瓦片全失败时自动切换。"""
        maps = workbench_engine.map_config({"map_provider": "leaflet"})
        self.assertEqual(maps["tile_crs"], "gcj02")
        self.assertIsNotNone(maps["fallback_tile"])
        self.assertEqual(maps["fallback_tile"]["crs"], "wgs84")   # 备用源不做 GCJ 转换
        self.assertIn("openstreetmap", maps["fallback_tile"]["url"])
        osm = workbench_engine.map_config({"map_provider": "leaflet",
                                           "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"})
        self.assertIsNone(osm["fallback_tile"])                   # 已经是 WGS84 就不用再备

    def test_map_provider_can_be_forced(self):
        forced_leaflet = workbench_engine.map_config({"amap_js_key": "k", "map_provider": "leaflet"})
        self.assertEqual(forced_leaflet["provider"], "leaflet")
        forced_none = workbench_engine.map_config({"amap_js_key": "k", "map_provider": "none"})
        self.assertFalse(forced_none["ready"])
        # 配了 key 且未强制时走 amap
        self.assertEqual(workbench_engine.map_config({"amap_js_key": "k"})["provider"], "amap")

    def test_tile_crs_follows_tile_host(self):
        amap_tiles = workbench_engine.map_config({})
        self.assertEqual(amap_tiles["tile_crs"], "gcj02")     # 高德瓦片是 GCJ-02
        osm_tiles = workbench_engine.map_config(
            {"tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"})
        self.assertEqual(osm_tiles["tile_crs"], "wgs84")      # OSM 是 WGS84

    def test_map_config_prefers_environment(self):
        import os
        os.environ["AMAP_JS_KEY"] = "env-key"
        try:
            self.assertEqual(workbench_engine.map_config({})["key"], "env-key")
            self.assertEqual(workbench_engine.map_config({})["provider"], "amap")
        finally:
            os.environ.pop("AMAP_JS_KEY", None)

    def test_session_endpoint_returns_token_but_no_engine_secret(self):
        status, envelope, _, _ = self.call("GET", "/api/session", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(envelope["data"]["token"], WORKBENCH_TOKEN)
        self.assertNotIn(TRIP_TOKEN, json.dumps(envelope))     # 引擎令牌绝不外泄
        self.assertTrue(envelope["data"]["base"].startswith("http://127.0.0.1:"))

    def test_api_requires_workbench_token(self):
        status, envelope, _, _ = self.call("GET", "/api/pois", token=None)
        self.assertEqual(status, 403)
        status, envelope, _, _ = self.call("GET", "/api/pois", token="nope")
        self.assertEqual(status, 403)

    def test_host_header_is_checked(self):
        self.client.request("GET", "/api/session", headers={"Host": "evil.example"})
        response = self.client.getresponse()
        response.read()
        self.assertEqual(response.status, 403)

    # ------------------------------------------------------------ 依赖发现

    def test_services_snapshot_reports_ready_and_missing(self):
        status, envelope, _, _ = self.call("GET", "/api/services")
        self.assertEqual(status, 200)
        ready = envelope["data"]["ready"]
        self.assertTrue(ready["trip_engine"])
        self.assertFalse(ready["rules_engine"])
        self.assertFalse(ready["route_adapter"])
        by_id = {item["module_id"]: item for item in envelope["data"]["services"]}
        self.assertEqual(by_id["rules_engine"]["health"], "not_running")
        self.assertIn("时序推演", by_id["rules_engine"]["purpose"])

    def test_missing_provider_key_has_actionable_service_detail(self):
        from unittest.mock import patch
        self.write_registry('route_adapter', 59999, 'x')
        with patch.object(self.services, '_probe', return_value={
            'ready': False, 'status': 'degraded', 'degraded_reason': 'provider_not_configured',
            'message': 'test-secret',
        }):
            info = self.services.status_of('route_adapter')
        self.assertFalse(info['ready'])
        self.assertIn('AMAP_WEB_KEY', info['detail'])
        self.assertIn('重新启动', info['detail'])
        self.assertNotIn('test-secret', json.dumps(info))

    def test_health_marks_degraded_when_optional_engines_missing(self):
        status, envelope, _, _ = self.call("GET", "/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(envelope["data"]["status"], "ok")
        self.assertTrue(envelope["data"]["degraded"])
        self.assertIn("rules_engine", envelope["data"]["degraded_reason"])

    def test_unreachable_upstream_is_reported_not_crashed(self):
        self.write_registry("rules_engine", 59998, "x")     # 注册了但没服务
        self.services._cache.clear()
        status, envelope, _, _ = self.call("GET", "/api/services")
        by_id = {item["module_id"]: item for item in envelope["data"]["services"]}
        self.assertEqual(by_id["rules_engine"]["health"], "unreachable")
        self.assertFalse(by_id["rules_engine"]["ready"])

    def test_missing_upstream_raises_upstream_error(self):
        with self.assertRaises(workbench_proxy.UpstreamError) as ctx:
            self.services.call("offline_kit", "GET", "/health")
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(ctx.exception.code, "UPSTREAM_DOWN")

    # ------------------------------------------------------------ 代理转发

    def test_proxies_poi_list_from_trip_engine(self):
        status, envelope, _, _ = self.call("GET", "/api/pois")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(envelope["data"]["pois"]), 4)
        first = envelope["data"]["pois"][0]
        for field in ("poi_id", "names", "category", "coordinate", "operating_rules"):
            self.assertIn(field, first)

    def test_proxies_anchor_catalogue_from_trip_engine(self):
        """① 的口岸/住宿候选必须经代理取自主数据，而不是前端写死。"""
        status, envelope, _, _ = self.call("GET", "/api/anchors")
        self.assertEqual(status, 200)
        data = envelope["data"]
        self.assertGreaterEqual(len(data["hubs"]), 7, data)
        self.assertGreaterEqual(len(data["hotels"]), 7, data)
        for field in ("id", "name_zh", "name_en", "name_pinyin", "lat", "lng"):
            self.assertIn(field, data["hubs"][0], data["hubs"][0])

    def test_poi_detail_carries_fields_the_drawer_needs(self):
        status, envelope, _, _ = self.call("GET", "/api/pois/sh_poi_00042")
        self.assertEqual(status, 200)
        rules = envelope["data"]["operating_rules"]
        self.assertIsNone(rules["last_entry_time"])          # 前端必须隐藏该行
        self.assertEqual(rules["closure_data_status"], "verified")
        self.assertTrue(rules["light_up"]["windows"])

    def test_create_trip_and_add_stop_through_proxy(self):
        payload = {
            "user_profile": {"party_composition": "family_kids", "pacing": "balanced",
                             "interests": ["history_culture"]},
            "duration_days": 2, "start_date": "2026-10-12", "daily_start_local": "09:00",
            "anchor_arrival": {"at": 1791819000, "location_name": "浦东机场 T2",
                               "coordinate": {"lat": 31.1443, "lng": 121.8083, "crs": "WGS84"}},
            "anchor_hotel": {"name_en": "Radisson Collection", "name_zh": "上海宏安瑞士大酒店",
                             "coordinate": {"lat": 31.2335, "lng": 121.4789, "crs": "WGS84"}},
        }
        status, envelope, _, _ = self.call("POST", "/api/trips", payload)
        self.assertEqual(status, 201, envelope)
        trip = envelope["data"]
        self.assertEqual(trip["anchor_arrival"]["activity_start_at"], 1791819000 + 5400)
        self.assertEqual(trip["user_profile"]["party_walk_multiplier"], 1.3)
        self.assertEqual(trip["days"][0]["day_status"], "arrival_only")

        status, envelope, _, _ = self.call("POST", f"/api/trips/{trip['trip_id']}/days/2/stops",
                                           {"poi_id": "sh_poi_00088"})
        self.assertEqual(status, 200, envelope)
        self.assertEqual(envelope["data"]["trip"]["version"], 2)
        self.assertEqual(envelope["data"]["trip"]["days"][1]["ordered_stops"][0]["planned_dwell_minutes"], 120)

        status, envelope, _, _ = self.call("GET", f"/api/trips/{trip['trip_id']}")
        self.assertEqual(status, 200)
        self.assertEqual(envelope["data"]["version"], 2)

        status, envelope, _, _ = self.call("PATCH", f"/api/trips/{trip['trip_id']}",
                                           {"daily_start_local": "08:30"})
        self.assertEqual(status, 200, envelope)
        self.assertEqual(envelope["data"]["days"][1]["daily_start_local"], "08:30")

        status, envelope, _, _ = self.call("DELETE",
                                           f"/api/trips/{trip['trip_id']}/days/2/stops/sh_poi_00088")
        self.assertEqual(status, 200, envelope)
        self.assertEqual(envelope["data"]["trip"]["days"][1]["ordered_stops"], [])

    def test_upstream_error_is_forwarded_with_contract_code(self):
        status, data, content_type = self.raw_call("GET", "/api/pois/sh_poi_99999")
        self.assertEqual(status, 404, data[:200])
        self.assertTrue(content_type.startswith("application/json"), content_type)
        self.assertEqual(json.loads(data.decode("utf-8"))["error"]["code"], "POI_NOT_FOUND")

    def test_engine_error_in_create_is_forwarded(self):
        payload = {"duration_days": 99, "user_profile": {"party_composition": "solo", "pacing": "balanced"},
                   "anchor_arrival": {"at": 1791819000, "location_name": "x", "coordinate": {"crs": "WGS84"}},
                   "anchor_hotel": {"name_en": "x", "name_zh": "x", "coordinate": {"crs": "WGS84"}}}
        status, data, content_type = self.raw_call("POST", "/api/trips", payload)
        self.assertEqual(status, 400, data[:200])
        self.assertTrue(content_type.startswith("application/json"), content_type)

    def test_bad_json_body_is_rejected(self):
        status, envelope, _, _ = self.call("POST", "/api/trips", raw=b"{bad json")
        self.assertEqual(status, 400)
        self.assertIn("JSON", envelope["error"]["message"])

    def test_unknown_route_is_404(self):
        status, envelope, _, _ = self.call("GET", "/api/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
