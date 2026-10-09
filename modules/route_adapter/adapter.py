"""Route Adapter 核心：归一化、降级、缓存、坐标、展示项数据来源（C1~C7）。"""
from __future__ import annotations

import time
import json
from concurrent.futures import ThreadPoolExecutor

try:
    from .cache import CallBudget, TTLCache
    from .geohash import encode as geohash_encode
    from .normalize import (LONG_TRANSFER_THRESHOLD_M, build_transfer_overhead, haversine_meters)
    from .providers import ProviderError, build_provider
    from .resilience import CircuitBreaker, RetryPolicy
except ImportError:  # 单模块独立测试时按顶层模块导入
    from cache import CallBudget, TTLCache
    from geohash import encode as geohash_encode
    from normalize import (LONG_TRANSFER_THRESHOLD_M, build_transfer_overhead, haversine_meters)
    from providers import ProviderError, build_provider
    from resilience import CircuitBreaker, RetryPolicy

_ROUTE_TTL = 1800
_DEGRADED_NOTICE = {"timeout": "degraded.direct_orientation",
                    "rate_limited": "degraded.direct_orientation",
                    "no_route": "degraded.direct_orientation",
                    "unsupported_city": "degraded.direct_orientation",
                    "partial_data": "degraded.partial_data"}


def _bucket(ts: int) -> str:
    t = time.localtime(int(ts))
    minutes = (t.tm_min // 30) * 30
    return time.strftime("%Y%m%d%H%M", (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, minutes, 0, 0, 0, -1))


def _as_point(coord):
    coord = coord or {}
    return {"lat": float(coord.get("lat")), "lng": float(coord.get("lng")), "crs": coord.get("crs", "WGS84")}


def _clean_endpoint(ep):
    return {**({'stop_id': ep['stop_id']} if ep.get('stop_id') else {}),
            "type": ep.get("type", "poi"), "poi_id": ep.get("poi_id"),
            "station_id": ep.get("station_id"), "name_zh": ep.get("name_zh"),
            "name_en": ep.get("name_en")}


class _ComputedVariant:
    def __init__(self, variant, segments, degraded, reason, polyline=None):
        self.variant = variant
        self.segments = segments or []
        self.polyline = polyline
        self.degraded = degraded
        self.reason = reason


class RouteAdapter:
    def __init__(self, config, station_lib, logger=None):
        self.config = config or {}
        self.logger = logger
        self.station_lib = station_lib
        provider_name = self.config.get("provider", "mock")
        provider_cfg = (self.config.get("providers") or {}).get(provider_name, {})
        self.provider = build_provider(provider_name, provider_cfg, station_lib)
        self.cache = TTLCache()
        self.breaker = CircuitBreaker()
        self.retry = RetryPolicy()
        self._drop_offs = {
            "sh_poi_00042": {
                "point": {"lat": 31.2415, "lng": 121.4875, "crs": "WGS84", "precision_m": 25},
                "desc_zh": "北京东路圆明园路口",
                "desc_en": "Intersection of Beijing East Rd & Yuanmingyuan Rd",
                "source": "curated", "selected_from": "curated",
            }
        }

    # ---------------------------------------------------------------- 缓存键
    def _cache_key(self, from_point, to_point, mode, ts):
        return ":".join([geohash_encode(from_point["lat"], from_point["lng"], 7),
                         geohash_encode(to_point["lat"], to_point["lng"], 7), mode, _bucket(ts)])

    # ---------------------------------------------------------------- 降级
    def _degraded_variant(self, mode, reason):
        return _ComputedVariant(
            variant={"mode": mode, "duration_seconds": None, "distance_meters": None,
                     "cost": None, "congestion_level": "unknown", "transfer_count": None,
                     "walking_distance_meters": None, "estimated_steps": None,
                     "highlight": False, "data_source": "degraded", "is_default_tab": False},
            segments=[], degraded=True, reason=reason)

    def _degraded_route(self, from_ep, to_ep, from_point, to_point, reason, ts, mode="transit"):
        straight = haversine_meters(from_point["lat"], from_point["lng"], to_point["lat"], to_point["lng"])
        return {
            "from": from_ep, "to": to_ep, "mode": mode, "variants": [],
            "distance_meters": int(round(straight)), "duration_seconds": None,
            "walking_distance_meters": None, "walking_duration_seconds": None,
            "estimated_steps": None, "transfer_count": None, "has_long_transfer": False,
            "long_transfer_threshold_m": LONG_TRANSFER_THRESHOLD_M, "transfer_overhead": None,
            "cost": None, "congestion_level": "unknown", "segments": [], "drop_off": None,
            "last_mile_walk_meters": None, "polyline": None, "crs": "WGS84",
            "cache": {"key": self._cache_key(from_point, to_point, mode, ts),
                      "ttl_seconds": 300, "hit": False},
            "data_source": "degraded", "degraded_reason": reason,
            "degraded_notice_key": _DEGRADED_NOTICE.get(reason, "degraded.partial_data"),
            "partial": True, "fetched_at": ts,
        }

    # ---------------------------------------------------------------- 三方调用
    def _call_provider(self, mode, from_point, to_point, party):
        try:
            return self.provider.compute(from_point, to_point, mode, party, {})
        except ProviderError as exc:
            self.breaker.record(True)
            if exc.reason == "timeout":
                return self._call_provider_retry(mode, from_point, to_point, party)
            raise
        except Exception:  # noqa: BLE001
            self.breaker.record(True)
            return self._call_provider_retry(mode, from_point, to_point, party)

    def _call_provider_retry(self, mode, from_point, to_point, party):
        for delay in self.retry.backoff_ms[:self.retry.max_retries]:
            time.sleep(delay / 1000.0)
            try:
                return self.provider.compute(from_point, to_point, mode, party, {})
            except ProviderError as exc:
                if exc.reason != "timeout":
                    raise
            except Exception:  # noqa: BLE001
                continue
        raise ProviderError("timeout")

    def _compute_variant(self, mode, from_point, to_point, party, ts, budget):
        key = self._cache_key(from_point, to_point, mode, ts)
        cached, hit = self.cache.get(key)
        if hit:
            segments = cached.get("__segments__") if isinstance(cached, dict) else None
            return _ComputedVariant(cached, segments, False, "none", cached.get('__polyline__'))
        if not budget.acquire():
            return self._degraded_variant(mode, "rate_limited")
        if not self.breaker.allow():
            return self._degraded_variant(mode, "timeout")
        try:
            result = self._call_provider(mode, from_point, to_point, party)
        except ProviderError as exc:
            # Expected provider failures are unavailable routes, not broken HTTP
            # connections. Keep raw provider messages out of responses and caches.
            if self.logger is not None:
                try:
                    self.logger.info("路线方式不可用：" + json.dumps(
                        {"mode": mode if mode in {"transit", "taxi", "walk", "bike"} else "unknown",
                         "reason": exc.reason if exc.reason in _DEGRADED_NOTICE else "partial_data",
                         "diagnostic": exc.diagnostic}, ensure_ascii=False))
                except Exception:  # 日志故障不能导致路线 HTTP 请求中断。
                    pass
            return self._degraded_variant(mode, exc.reason)
        self.breaker.record(False)
        segments = result.get("segments")
        variant = self._make_variant(result)
        cache_value = dict(variant)
        if segments is not None:
            cache_value["__segments__"] = segments
        cache_value['__polyline__'] = result.get('polyline')
        self.cache.set(key, cache_value, _ROUTE_TTL)
        return _ComputedVariant(variant, segments, False, "none", result.get('polyline'))

    def _make_variant(self, result):
        mode = result["mode"]
        dist = result.get("distance_meters")
        highlight = bool(mode in ("walk", "bike") and dist is not None and dist <= 3000)
        return {
            "mode": mode,
            "duration_seconds": result.get("duration_seconds"),
            "distance_meters": dist,
            "cost": result.get("cost"),
            "congestion_level": result.get("congestion_level", "unknown"),
            "transfer_count": result.get("transfer_count"),
            "walking_distance_meters": result.get("walking_distance_meters"),
            "estimated_steps": result.get("estimated_steps"),
            "highlight": highlight,
            "data_source": result.get("data_source", self.provider.source),
            "is_default_tab": False,
        }

    # ---------------------------------------------------------------- 主入口
    def compute_route(self, from_ep, to_ep, modes, party, prefer_taxi=None, departure_ts=None,
                      mock_degrade=False, budget=None):
        ts = int(time.time()) if departure_ts is None else int(departure_ts)
        from_point = _as_point(from_ep.get("coordinate"))
        to_point = _as_point(to_ep.get("coordinate"))
        from_clean = _clean_endpoint(from_ep)
        to_clean = _clean_endpoint(to_ep)
        if mock_degrade:
            return self._degraded_route(from_clean, to_clean, from_point, to_point, "timeout", ts)

        modes = list(modes or ["transit"])
        budget = budget or CallBudget(4)
        transit_result = None
        if "transit" in modes:
            transit_result = self._compute_variant("transit", from_point, to_point, party, ts, budget)

        primary = "transit" if "transit" in modes else modes[0]
        other_modes = [m for m in modes if m != "transit"]
        other_results = {}
        if other_modes:
            with ThreadPoolExecutor(max_workers=min(4, len(other_modes))) as pool:
                futures = {m: pool.submit(self._compute_variant, m, from_point, to_point, party, ts, budget)
                           for m in other_modes}
                other_results = {m: f.result() for m, f in futures.items()}

        # A missing transit plan does not imply that walking/driving is unavailable.
        # Preserve each requested mode, while keeping the original route selection.
        results = {**other_results}
        if transit_result is not None:
            results["transit"] = transit_result
        if all(results[m].degraded for m in modes):
            return self._degraded_route(from_clean, to_clean, from_point, to_point,
                                        results[primary].reason, ts, mode=primary)

        variants = []
        segments = results[primary].segments or []
        any_degraded = False
        for mode in modes:
            r = transit_result if mode == "transit" else other_results[mode]
            if r.degraded:
                any_degraded = True
            variants.append(r.variant)

        preference = self.config.get("prefer_taxi", False) if prefer_taxi is None else prefer_taxi
        available = [v["mode"] for v in variants if v.get("duration_seconds") is not None]
        default_mode = ("taxi" if preference and "taxi" in available else
                        primary if primary in available else
                        "walk" if "walk" in available else available[0] if available else primary)
        # Cache only provider data; presentation preference belongs to this request.
        variants = [{**{k: value for k, value in v.items() if not k.startswith('__')},
                     "is_default_tab": v["mode"] == default_mode} for v in variants]
        pv = next(v for v in variants if v["mode"] == primary)
        has_long = False
        for seg in segments:
            if seg.get("kind") == "transfer" and seg.get("transfer"):
                tw = seg["transfer"].get("walking_distance_meters")
                if tw is not None and tw >= LONG_TRANSFER_THRESHOLD_M:
                    has_long = True

        route = {
            "from": from_clean, "to": to_clean, "mode": primary, "variants": variants,
            "distance_meters": pv.get("distance_meters"),
            "duration_seconds": pv.get("duration_seconds"),
            "walking_distance_meters": pv.get("walking_distance_meters"),
            "walking_duration_seconds": None,
            "estimated_steps": pv.get("estimated_steps"),
            "transfer_count": pv.get("transfer_count"),
            "has_long_transfer": has_long,
            "long_transfer_threshold_m": LONG_TRANSFER_THRESHOLD_M,
            "transfer_overhead": build_transfer_overhead() if has_long else None,
            "cost": pv.get("cost"),
            "congestion_level": pv.get("congestion_level", "unknown"),
            "segments": segments,
            "drop_off": self.get_drop_off(to_ep.get("poi_id")),
            "last_mile_walk_meters": self._last_mile(segments),
            "polyline": results[primary].polyline, "crs": "WGS84",
            "cache": {"key": self._cache_key(from_point, to_point, primary, ts),
                      "ttl_seconds": _ROUTE_TTL, "hit": False},
            "data_source": self.provider.source,
            "degraded_reason": results[primary].reason if results[primary].degraded else "partial_data" if any_degraded else "none",
            "degraded_notice_key": _DEGRADED_NOTICE.get(results[primary].reason, "degraded.partial_data") if results[primary].degraded else "degraded.partial_data" if any_degraded else None,
            "partial": any_degraded,
            "fetched_at": ts,
        }
        route["walking_duration_seconds"] = self._walk_duration(segments)
        return route

    def _last_mile(self, segments):
        for seg in reversed(segments):
            if seg.get("kind") == "walk":
                return seg.get("distance_meters")
        return None

    def _walk_duration(self, segments):
        total = 0
        for seg in segments:
            if seg.get("kind") == "walk" and seg.get("duration_seconds") is not None:
                total += seg["duration_seconds"]
        return total or None

    # ---------------------------------------------------------------- 站台库与落客
    def get_station(self, station_id):
        return self.station_lib.get(station_id)

    def get_drop_off(self, poi_id):
        return self._drop_offs.get(poi_id)
