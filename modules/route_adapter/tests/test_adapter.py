import common  # noqa: F401
import os
import unittest
from unittest.mock import patch

from adapter import RouteAdapter
from cache import CallBudget
from normalize import LONG_TRANSFER_THRESHOLD_M
from providers import AmapProvider, BaiduProvider, TencentProvider, ProviderError, build_provider
from stations import CuratedStationLibrary

_MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATION_PATH = os.path.join(_MODULE, "data", "curated_stations.json")

FROM = {"type": "poi", "poi_id": "sh_poi_00042", "station_id": None, "name_zh": "外滩",
        "name_en": "The Bund", "coordinate": {"lat": 31.2397, "lng": 121.49, "crs": "WGS84"}}
TO = {"type": "poi", "poi_id": "sh_poi_00088", "station_id": None, "name_zh": "上海博物馆",
      "name_en": "Shanghai Museum", "coordinate": {"lat": 31.2304, "lng": 121.4737, "crs": "WGS84"}}
FAR_TO = {"type": "poi", "poi_id": "sh_poi_00119", "station_id": None, "name_zh": "迪士尼",
          "name_en": "Disney", "coordinate": {"lat": 31.1443, "lng": 121.6572, "crs": "WGS84"}}


def _adapter(config=None):
    lib = CuratedStationLibrary(_STATION_PATH)
    return RouteAdapter(config or {"provider": "mock"}, lib)


class AdapterTests(unittest.TestCase):
    def test_selected_mode_keeps_its_own_instructions_including_cache(self):
        adapter=_adapter()
        walk_segment={'kind':'walk','duration_seconds':90,'distance_meters':100,'walk_note_zh':'向东步行'}
        def compute(_from,_to,mode,*args):
            return {'mode':mode,'distance_meters':100,'duration_seconds':90,
                    'segments':[walk_segment] if mode=='walk' else
                    [{'kind':'ride','duration_seconds':90}] if mode=='transit' else []}
        with patch.object(adapter.provider,'compute',side_effect=compute):
            walk=adapter.compute_route(FROM,TO,['walk'],'solo')
            cached=adapter.compute_route(FROM,TO,['walk'],'solo')
            mixed=adapter.compute_route(FROM,TO,['walk','taxi'],'solo')
            taxi=adapter.compute_route(FROM,TO,['taxi'],'solo')
        self.assertEqual(walk['segments'],[walk_segment])
        self.assertEqual(cached['segments'],[walk_segment])
        self.assertEqual(mixed['segments'],[walk_segment])
        self.assertEqual(walk['walking_duration_seconds'],90)
        self.assertEqual(taxi['segments'],[])
        self.assertEqual(common.validate_route(walk),[])

    def test_route_geometry_survives_cache_without_leaking_to_variants(self):
        adapter=_adapter()
        response={'mode':'walk','distance_meters':100,'duration_seconds':90,'data_source':'mock',
                  'segments':[], 'polyline':'121.47,31.23;121.471,31.231'}
        with patch.object(adapter.provider,'compute',return_value=response) as provider:
            first=adapter.compute_route(FROM,TO,['walk'],'solo')
            cached=adapter.compute_route(FROM,TO,['walk'],'solo')
        self.assertEqual(provider.call_count,1)
        self.assertEqual(first['polyline'],response['polyline'])
        self.assertEqual(cached['polyline'],response['polyline'])
        self.assertEqual(common.validate_route(cached),[])

    def test_mock_route_passes_schema(self):
        route = _adapter().compute_route(FROM, TO, ["transit", "taxi", "walk"], "solo")
        self.assertEqual(common.validate_route(route), [])
        self.assertEqual(route["data_source"], "mock")
        self.assertEqual(route["degraded_reason"], "none")
        self.assertEqual(len(route["variants"]), 3)

    def test_degraded_route_nulls_not_zero(self):
        route = _adapter().compute_route(FROM, TO, ["transit"], "solo", mock_degrade=True)
        self.assertEqual(common.validate_route(route), [])
        self.assertEqual(route["data_source"], "degraded")
        self.assertEqual(route["degraded_reason"], "timeout")
        self.assertIsNotNone(route["degraded_notice_key"])
        self.assertTrue(route["partial"])
        self.assertIsNone(route["duration_seconds"])
        self.assertIsNone(route["cost"])
        self.assertIsNone(route["transfer_count"])
        self.assertEqual(route["variants"], [])

    def test_provider_error_returns_degraded_route_instead_of_escaping(self):
        for reason in ['unsupported_city', 'partial_data', 'rate_limited', 'no_route', 'timeout']:
            with self.subTest(reason=reason):
                adapter = _adapter()
                adapter.retry.max_retries = 0
                with patch.object(adapter.provider, 'compute', side_effect=ProviderError(reason, 'test-secret')):
                    route = adapter.compute_route(FROM, TO, ['transit', 'taxi', 'walk'], 'solo')
                self.assertEqual(common.validate_route(route), [])
                self.assertEqual(route['data_source'], 'degraded')
                self.assertEqual(route['degraded_reason'], reason)
                self.assertIsNone(route['duration_seconds'])
                self.assertNotIn('test-secret', str(route))

    def test_long_transfer_detected_with_overhead(self):
        route = _adapter().compute_route(FROM, FAR_TO, ["transit"], "solo")
        self.assertEqual(common.validate_route(route), [])
        self.assertTrue(route["has_long_transfer"])
        self.assertIsNotNone(route["transfer_overhead"])
        self.assertEqual(route["transfer_overhead"]["factor"], 1.3)
        transfer_walk = [s["transfer"]["walking_distance_meters"] for s in route["segments"]
                         if s.get("kind") == "transfer"][0]
        self.assertGreaterEqual(transfer_walk, LONG_TRANSFER_THRESHOLD_M)

    def test_transit_no_route_keeps_walk_and_taxi_options(self):
        adapter = _adapter()
        original = adapter.provider.compute
        calls = []

        def without_transit(*args, **kwargs):
            calls.append(args[2])
            if args[2] == 'transit':
                raise ProviderError('no_route')
            return original(*args, **kwargs)

        with patch.object(adapter.provider, 'compute', side_effect=without_transit):
            route = adapter.compute_route(FROM, TO, ['transit', 'taxi', 'walk'], 'solo')
        self.assertEqual(set(calls), {'transit', 'taxi', 'walk'})
        self.assertEqual(common.validate_route(route), [])
        self.assertIsNone(route['duration_seconds'])  # 不替用户选择其他方式
        self.assertEqual(route['mode'], 'transit')
        self.assertTrue(route['partial'])
        self.assertEqual(route['degraded_reason'], 'no_route')
        self.assertEqual(route['data_source'], 'mock')
        variants = {v['mode']: v for v in route['variants']}
        self.assertIsNone(variants['transit']['duration_seconds'])
        self.assertGreater(variants['walk']['duration_seconds'], 0)
        self.assertGreater(variants['taxi']['duration_seconds'], 0)
        self.assertFalse(variants['transit']['is_default_tab'])
        self.assertTrue(variants['walk']['is_default_tab'])

    def test_transit_only_no_route_still_degrades(self):
        adapter = _adapter()
        with patch.object(adapter.provider, 'compute', side_effect=ProviderError('no_route')):
            route = adapter.compute_route(FROM, TO, ['transit'], 'solo')
        self.assertEqual(common.validate_route(route), [])
        self.assertEqual(route['data_source'], 'degraded')
        self.assertEqual(route['degraded_reason'], 'no_route')
        self.assertEqual(route['variants'], [])

    def test_failure_log_only_contains_safe_diagnostic(self):
        logs = []
        class Logger:
            def info(self, message):
                logs.append(message)
        adapter = _adapter()
        adapter.logger = Logger()
        error = ProviderError('partial_data', 'test-secret-key', diagnostic={
            'category':'service_error','provider_code':'10005','url':'test-secret-url'})
        with patch.object(adapter.provider, 'compute', side_effect=error):
            route = adapter.compute_route(FROM, TO, ['walk'], 'solo')
        self.assertEqual(route['data_source'], 'degraded')
        self.assertIn('10005', logs[0])
        self.assertNotIn('test-secret', str(logs))

    def test_transit_no_route_keeps_walk_and_taxi_options(self):
        adapter = _adapter()
        original = adapter.provider.compute
        calls = []

        def without_transit(*args, **kwargs):
            calls.append(args[2])
            if args[2] == 'transit':
                raise ProviderError('no_route')
            return original(*args, **kwargs)

        with patch.object(adapter.provider, 'compute', side_effect=without_transit):
            route = adapter.compute_route(FROM, TO, ['transit', 'taxi', 'walk'], 'solo')
        self.assertEqual(set(calls), {'transit', 'taxi', 'walk'})
        self.assertEqual(common.validate_route(route), [])
        self.assertIsNone(route['duration_seconds'])  # 不替用户选择其他方式
        self.assertEqual(route['mode'], 'transit')
        self.assertTrue(route['partial'])
        self.assertEqual(route['degraded_reason'], 'no_route')
        self.assertEqual(route['data_source'], 'mock')
        variants = {v['mode']: v for v in route['variants']}
        self.assertIsNone(variants['transit']['duration_seconds'])
        self.assertGreater(variants['walk']['duration_seconds'], 0)
        self.assertGreater(variants['taxi']['duration_seconds'], 0)
        self.assertFalse(variants['transit']['is_default_tab'])
        self.assertTrue(variants['walk']['is_default_tab'])

    def test_transit_only_no_route_still_degrades(self):
        adapter = _adapter()
        with patch.object(adapter.provider, 'compute', side_effect=ProviderError('no_route')):
            route = adapter.compute_route(FROM, TO, ['transit'], 'solo')
        self.assertEqual(common.validate_route(route), [])
        self.assertEqual(route['data_source'], 'degraded')
        self.assertEqual(route['degraded_reason'], 'no_route')
        self.assertEqual(route['variants'], [])

    def test_prefer_taxi_sets_default_tab(self):
        route = _adapter({"provider": "mock", "prefer_taxi": True}).compute_route(
            FROM, TO, ["transit", "taxi", "walk"], "family_kids", prefer_taxi=True)
        taxi = [v for v in route["variants"] if v["mode"] == "taxi"][0]
        self.assertTrue(taxi["is_default_tab"])

    def test_request_preference_overrides_config_and_cached_variants(self):
        adapter = _adapter({"provider": "mock", "prefer_taxi": False})
        for preference, expected in [(True, "taxi"), (False, "transit"), (True, "taxi")]:
            route = adapter.compute_route(FROM, TO, ["transit", "taxi"], "solo",
                                          prefer_taxi=preference, departure_ts=1791819600)
            self.assertEqual([v["mode"] for v in route["variants"] if v["is_default_tab"]], [expected])
            self.assertTrue(all("__segments__" not in v for v in route["variants"]))
        adapter.config["prefer_taxi"] = True
        route = adapter.compute_route(FROM, TO, ["taxi", "transit"], "solo", prefer_taxi=False)
        self.assertEqual(route["mode"], "transit")
        transit = next(v for v in route["variants"] if v["mode"] == "transit")
        self.assertTrue(transit["is_default_tab"])
        self.assertEqual(route["duration_seconds"], transit["duration_seconds"])

    def test_walk_highlight_under_3km(self):
        route = _adapter().compute_route(FROM, TO, ["walk"], "solo")
        self.assertEqual(route["mode"], "walk")
        walk = route["variants"][0]
        self.assertEqual(walk["mode"], "walk")
        self.assertTrue(walk["highlight"])

    def test_call_budget_caps_provider_calls(self):
        adapter = _adapter()
        budget = CallBudget(4)
        dest_a = {"type": "poi", "poi_id": "p_a", "station_id": None, "name_zh": "A", "name_en": "A",
                  "coordinate": {"lat": 31.2304, "lng": 121.4737, "crs": "WGS84"}}
        dest_b = {"type": "poi", "poi_id": "p_b", "station_id": None, "name_zh": "B", "name_en": "B",
                  "coordinate": {"lat": 31.2200, "lng": 121.4600, "crs": "WGS84"}}
        dest_c = {"type": "poi", "poi_id": "p_c", "station_id": None, "name_zh": "C", "name_en": "C",
                  "coordinate": {"lat": 31.2100, "lng": 121.4500, "crs": "WGS84"}}
        adapter.compute_route(FROM, dest_a, ["transit", "taxi", "walk"], "solo", budget=budget)
        adapter.compute_route(FROM, dest_b, ["transit"], "solo", budget=budget)
        third = adapter.compute_route(FROM, dest_c, ["transit"], "solo", budget=budget)
        self.assertEqual(third["data_source"], "degraded")

    def test_cache_hit_avoids_provider_call(self):
        adapter = _adapter()
        calls = []
        original = adapter.provider.compute

        def counting(*args, **kwargs):
            calls.append(args[2])
            return original(*args, **kwargs)

        adapter.provider.compute = counting
        adapter.compute_route(FROM, TO, ["transit", "taxi", "walk"], "solo", departure_ts=1791819600)
        first_count = len(calls)
        adapter.compute_route(FROM, TO, ["transit", "taxi", "walk"], "solo", departure_ts=1791819600)
        self.assertEqual(len(calls), first_count)


class ProviderMappingTests(unittest.TestCase):
    def test_provider_switch_by_config(self):
        lib = CuratedStationLibrary(_STATION_PATH)
        self.assertEqual(build_provider("mock", {}, lib).name, "mock")
        self.assertIsInstance(build_provider("amap", {}, lib), AmapProvider)
        self.assertIsInstance(build_provider("tencent", {}, lib), TencentProvider)
        self.assertIsInstance(build_provider("baidu", {}, lib), BaiduProvider)

    def test_real_providers_normalize_consistently(self):
        payload = {"duration": 1200, "distance": 3000, "cost": 4, "transfer_count": 1,
                   "walking_distance": 500, "congestion_level": "low"}
        from_point = {"lat": 31.2397, "lng": 121.49, "crs": "GCJ-02"}
        to_point = {"lat": 31.2304, "lng": 121.4737, "crs": "WGS84"}
        amap = AmapProvider({})
        tencent = TencentProvider({})
        baidu = BaiduProvider({})
        a = amap._normalize_direction(payload, from_point, to_point, "transit", "solo")
        t = tencent._normalize_direction(payload, from_point, to_point, "transit", "solo")
        b = baidu._normalize_direction(payload, from_point, to_point, "transit", "solo")
        self.assertEqual(set(a.keys()), set(t.keys()))
        self.assertEqual(set(t.keys()), set(b.keys()))
        self.assertEqual(a["data_source"], "amap")
        self.assertEqual(t["data_source"], "tencent")
        self.assertEqual(b["data_source"], "baidu")

    def test_provider_crs(self):
        self.assertEqual(AmapProvider({}).provider_crs, "GCJ-02")
        self.assertEqual(TencentProvider({}).provider_crs, "GCJ-02")
        self.assertEqual(BaiduProvider({}).provider_crs, "BD-09")


if __name__ == "__main__":
    unittest.main()
