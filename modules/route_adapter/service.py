"""route_adapter 的 HTTP 服务：端口、注册表、令牌、依赖等待与业务端点（C7）。"""
from __future__ import annotations

import hmac
import json
import re
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urlerror

try:
    from .adapter import RouteAdapter
    from .cache import CallBudget
    from .resilience import IdempotencyStore
    from .stations import CuratedStationLibrary
except ImportError:  # 单模块独立测试时按顶层模块导入
    from adapter import RouteAdapter
    from cache import CallBudget
    from resilience import IdempotencyStore
    from stations import CuratedStationLibrary

# 与 registry 保持一致；这里延迟导入以兼容无 contracts 包的单独调试环境。
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from contracts.runtime import registry as _registry
except Exception:  # noqa: BLE001
    _registry = None


COMPUTE_RE = re.compile(r"^/trips/([^/]+)/days/([0-9]+)/routes:compute$")
STATION_RE = re.compile(r"^/stations/([^/]+)$")
DROP_OFF_RE = re.compile(r"^/pois/([^/]+)/drop-off$")


class RouteAdapterService:
    module_id = "route_adapter"
    dependencies = ["trip_engine"]

    def __init__(self, config, data_dir, workspace_root, logger, module_dir):
        import os
        cfg = dict(config or {})
        if "provider" not in cfg:
            cfg["provider"] = os.environ.get("ROUTE_PROVIDER", "mock")
        if os.environ.get("MOCK_DEGRADE") == "1":
            cfg["mock_degrade"] = True
        self.config = cfg
        self.data_dir = Path(data_dir)
        self.workspace_root = Path(workspace_root)
        self.logger = logger
        self.module_dir = Path(module_dir)
        self.token = _registry.new_token() if _registry else _fallback_token()
        self.port = 0
        self.started_at = int(time.time())
        self.upstream_ids = list(self.dependencies)   # 固定的依赖清单：刷新时用它，不随注册表增删
        self.upstreams = {}
        self.upstream_down = False
        self.degraded_reason = None
        self._httpd = None
        self._http_thread = None
        self._monitor_thread = None
        self._stop_event = threading.Event()
        station_path = self.module_dir / "data" / "curated_stations.json"
        self.station_lib = CuratedStationLibrary(station_path)
        self.adapter = RouteAdapter(self.config, self.station_lib, logger=self.logger)
        self.idempotency = IdempotencyStore()
        self.adapter.idempotency = self.idempotency

    # ------------------------------------------------------------ 生命周期
    def start(self):
        if not _registry:
            raise RuntimeError("缺少 contracts.runtime.registry，无法注册端口")
        # 端口粘性：没有显式配置时复用上一次登记的端口，书签/深链在重启后依然有效
        port = _registry.resolve_port(self.config, self.module_id, self.workspace_root)
        _registry.check_no_live_instance(self.workspace_root, self.module_id)
        for dep in self.dependencies:
            reg = self._wait_for_upstream(dep, timeout=30.0)
            self.upstreams[dep] = reg
        handler = _make_handler(self)
        try:
            self._httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as exc:
            raise RuntimeError(f"端口 {port or '自动'} 绑定失败：{exc}") from exc
        self.port = self._httpd.server_port
        _registry.write(_registry.build_registration(
            self.module_id, self.port, self.token, depends_on=self.dependencies,
            endpoints=["/health", "/trips/{id}/days/{d}/routes:compute",
                       "/stations/{station_id}", "/pois/{poi_id}/drop-off"]),
            self.workspace_root)
        self._http_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._http_thread.start()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._log(f"route_adapter 已启动：http://127.0.0.1:{self.port}，provider={self.config.get('provider', 'mock')}")

    def stop(self):
        self._stop_event.set()
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if _registry:
            try:
                _registry.remove(self.workspace_root, self.module_id)
            except Exception:  # noqa: BLE001
                pass
        self._log("route_adapter 已停止")

    def _log(self, message):
        try:
            if hasattr(self.logger, "info"):
                self.logger.info(str(message))
            elif callable(self.logger):
                self.logger(str(message))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 依赖
    def _wait_for_upstream(self, module_id, timeout):
        deadline = time.monotonic() + timeout
        interval = 0.2
        while time.monotonic() < deadline:
            reg = _registry.try_read(self.workspace_root, module_id)
            if reg is not None:
                health = _registry.probe_health(reg.base_url, timeout=0.5)
                if health is not None and health.get("status") in ("ok", "degraded", None):
                    return reg
            time.sleep(interval)
            interval = min(interval * 2, 1.0)
        raise RuntimeError(f"依赖 {module_id} 在 {timeout:.0f}s 内未就绪")

    def _monitor_loop(self):
        while not self._stop_event.wait(2.0):
            # 每轮重读注册表：上游重启会换端口，抱着启动时的快照会永久显示 degraded
            self._refresh_upstreams()
            down = len(self.upstreams) < len(self.upstream_ids)
            for module_id, reg in list(self.upstreams.items()):
                if _registry.probe_health(reg.base_url, timeout=0.5) is None:
                    down = True
                    break
            self.upstream_down = down
            self.degraded_reason = "upstream_down" if down else None

    def _refresh_upstreams(self):
        """重新解析上游登记信息（上游重启后端口与令牌都会变）。"""
        current = _registry.refresh(self.workspace_root, self.upstream_ids)
        self.upstreams = {module_id: reg for module_id, reg in current.items() if reg is not None}
        return self.upstreams

    # ------------------------------------------------------------ 上游调用
    def _call_trip_engine(self, method, path, payload=None):
        # 调用前先刷新：上游刚重启时监控循环可能还没跑到，不能让请求撞上死端口。
        # 这里不看缓存出来的 upstream_down——它是给 /health 看的信号，
        # 真正算不算「上游不可用」由这次调用本身决定。
        self._refresh_upstreams()
        reg = self.upstreams.get("trip_engine")
        if not reg:
            raise _UpstreamDown("trip_engine")
        try:
            return _registry.call_json(reg, method, path, payload)
        except _registry.RegistryError as exc:
            # 注册文件可能还残留着（对方崩溃没清理），连接失败同样按上游不可用上报，不要漏成 500
            raise _UpstreamDown("trip_engine") from exc

    # ------------------------------------------------------------ 业务
    def health_payload(self):
        provider = self.adapter.provider
        missing_key = provider.name in {"amap", "tencent", "baidu"} and not provider.api_key
        degraded = self.upstream_down or missing_key
        status = "degraded" if degraded else "ok"
        return {
            "module_id": self.module_id,
            "status": status,
            "contract_version": _registry.CONTRACT_VERSION,
            "ready": not missing_key,
            "started_at": self.started_at,
            "degraded": degraded,
            "degraded_reason": "provider_not_configured" if missing_key else self.degraded_reason,
            "upstreams": {m: ("down" if self.upstream_down else "up") for m in self.upstream_ids},
        }

    def compute_routes(self, trip_id, day_index, body, idempotency_key=None):
        if idempotency_key:
            cached = self.idempotency.get(idempotency_key)
            if cached is not None:
                return cached

        party = body.get("party_composition") or self.config.get("party_composition", "solo")
        prefer_taxi = bool(body.get("prefer_taxi", self.config.get("prefer_taxi", False)))
        modes = body.get("modes") or ["transit", "taxi", "walk"]
        mock_degrade = bool(self.config.get("mock_degrade", False))

        if body.get("from") and body.get("to"):
            segments = [(_endpoint_from_body(body["from"]), _endpoint_from_body(body["to"]))]
        else:
            segments = self._trip_day_segments(trip_id, day_index)
        if body.get("segment_index") is not None:
            index = body["segment_index"]
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(segments):
                raise ValueError("segment_index 超出当日区间范围")
            segments = [segments[index]]

        if not segments:
            return {"routes": [], "call_budget": {"used": 0, "max": 4}}

        budget = CallBudget(4)
        routes = []
        for from_ep, to_ep in segments:
            a, b = from_ep.get('coordinate') or {}, to_ep.get('coordinate') or {}
            if a and b and all(a.get(k) == b.get(k) for k in ('lat', 'lng', 'crs')):
                # 显式口岸/住宿与默认边界重合时仍保留区段位置，耗时为零，无需请求提供商。
                clean = lambda ep: {k: v for k, v in ep.items() if k != 'coordinate'}
                routes.append({'from': clean(from_ep), 'to': clean(to_ep), 'mode': 'walk',
                               'distance_meters': 0, 'duration_seconds': 0,
                               'walking_distance_meters': 0, 'walking_duration_seconds': 0,
                               'data_source': 'curated', 'degraded_reason': 'none',
                               'fetched_at': int(time.time()), 'segments': [], 'variants': [],
                               'has_long_transfer': False})
                continue
            routes.append(self.adapter.compute_route(
                from_ep, to_ep, modes, party, prefer_taxi=prefer_taxi,
                mock_degrade=mock_degrade, budget=budget))
        result = {"routes": routes, "call_budget": {"used": budget.used, "max": budget.max_calls}}
        if idempotency_key:
            self.idempotency.put(idempotency_key, result)
        return result

    def _trip_day_segments(self, trip_id, day_index):
        trip = self._fetch_trip(trip_id)
        days = trip.get("days") or []
        day = None
        for d in days:
            if d.get("day_index") == int(day_index):
                day = d
                break
        if not day:
            return []
        stops = day.get("ordered_stops") or []
        anchors = self._anchors(trip, day_index)
        coords = []
        for stop in stops:
            coord = self._resolve_stop_coordinate(trip, stop)
            if coord:
                coords.append(self._endpoint_for_stop(stop, coord))
        if anchors.get("start"):
            coords.insert(0, anchors["start"])
        if anchors.get("end"):
            coords.append(anchors["end"])
        segments = []
        for i in range(len(coords) - 1):
            segments.append((coords[i], coords[i + 1]))
        return segments

    def _fetch_trip(self, trip_id):
        try:
            envelope = self._call_trip_engine("GET", f"/trips/{trip_id}")
        except _UpstreamDown as exc:
            raise exc
        except Exception as exc:  # noqa: BLE001
            raise _UpstreamError(str(exc))
        if isinstance(envelope, dict) and envelope.get("ok") is True:
            return envelope.get("data") or {}
        if isinstance(envelope, dict) and "trip_id" in envelope:
            return envelope
        raise _UpstreamError("trip_engine 返回结构非法")

    def _anchors(self, trip, day_index=1):
        from core.trip_points import resolve_day_points
        return resolve_day_points(trip).get(int(day_index), {'start': None, 'end': None})

    def _resolve_stop_coordinate(self, trip, stop):
        if stop.get("coordinate"):
            return stop["coordinate"]
        poi_id = stop.get("poi_id")
        if poi_id:
            try:
                envelope = self._call_trip_engine("GET", f"/pois/{poi_id}")
            except Exception:  # noqa: BLE001
                return None
            data = (envelope or {}).get("data") if isinstance(envelope, dict) else envelope
            if isinstance(data, dict) and data.get("coordinate"):
                stop["name_zh"] = (data.get("names") or {}).get("zh-Hans")
                stop["name_en"] = (data.get("names") or {}).get("en")
                return data["coordinate"]
            return None
        return None

    def _endpoint_for_stop(self, stop, coord):
        return {**({'stop_id': stop['stop_id']} if stop.get('stop_id') else {}),
                "type": stop.get("stop_type") or "poi", "poi_id": stop.get("poi_id"),
                "station_id": None, "name_zh": stop.get("name_zh"),
                "name_en": stop.get("name_en"), "coordinate": coord}

    def get_station(self, station_id):
        station = self.adapter.get_station(station_id)
        return station

    def get_drop_off(self, poi_id):
        drop = self.adapter.get_drop_off(poi_id)
        return drop


class _UpstreamDown(RuntimeError):
    pass


class _UpstreamError(RuntimeError):
    pass


def _fallback_token():
    import secrets
    return secrets.token_urlsafe(32)


def _endpoint_from_body(value):
    coord = value.get("coordinate") or {}
    return {
        "type": value.get("type") or "poi",
        "poi_id": value.get("poi_id"),
        "station_id": value.get("station_id"),
        "name_zh": value.get("name_zh"),
        "name_en": value.get("name_en"),
        "coordinate": {"lat": coord.get("lat"), "lng": coord.get("lng"),
                       "crs": coord.get("crs", "WGS84"), "precision_m": coord.get("precision_m", 50)},
    }


def _make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "inboundroute-route-adapter/0.1"

        def log_message(self, fmt, *args):  # noqa: A003
            return

        # -- 工具
        def _json_body(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return {}

        def _send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Contract-Version", _registry.CONTRACT_VERSION)
            self.end_headers()
            self.wfile.write(body)

        def _success(self, data):
            return {"ok": True, "data": data,
                    "meta": {"version": _registry.CONTRACT_VERSION, "server_time": int(time.time())}}

        def _error(self, status, code, message_key, message, retryable=False, details=None):
            return {"ok": False,
                    "error": {"code": code, "message_key": message_key, "message": message,
                              "details": details or {}, "retryable": retryable,
                              "trace_id": uuid.uuid4().hex}}

        def _check_token(self):
            given = self.headers.get("X-Module-Token", "")
            if not hmac.compare_digest(given, service.token):
                self._send_json(403, self._error(403, "FORBIDDEN", "error.forbidden",
                                                 "invalid module token"))
                return False
            return True

        def _path(self):
            p = self.path.split("?", 1)[0]
            if p.startswith("/api/v1"):
                p = p[len("/api/v1"):]
            return p or "/"

        # -- 路由
        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def _dispatch(self, method):
            path = self._path()
            if path == "/health":
                self._send_json(200, service.health_payload())
                return
            if not self._check_token():
                return

            if method == "GET":
                m = STATION_RE.match(path)
                if m:
                    station = service.get_station(m.group(1))
                    if station is None:
                        self._send_json(404, self._error(404, "TRIP_NOT_FOUND",
                                                         "error.trip_not_found", "station not found"))
                        return
                    self._send_json(200, self._success(station))
                    return
                m = DROP_OFF_RE.match(path)
                if m:
                    drop = service.get_drop_off(m.group(1))
                    if drop is None:
                        self._send_json(404, self._error(404, "TRIP_NOT_FOUND",
                                                         "error.trip_not_found", "drop-off not found"))
                        return
                    self._send_json(200, self._success(drop))
                    return

            if method == "POST":
                m = COMPUTE_RE.match(path)
                if m:
                    if service.upstream_down:
                        self._send_json(503, self._error(503, "UPSTREAM_TIMEOUT",
                                                         "error.upstream_timeout",
                                                         "upstream trip_engine unavailable",
                                                         retryable=True,
                                                         details={"upstream": "trip_engine"}))
                        return
                    body = self._json_body()
                    idem = self.headers.get("Idempotency-Key")
                    try:
                        data = service.compute_routes(m.group(1), int(m.group(2)), body, idem)
                    except (ValueError, TypeError, KeyError) as exc:
                        self._send_json(400, self._error(400, "BAD_REQUEST", "error.bad_request", str(exc)))
                        return
                    except _UpstreamDown:
                        self._send_json(503, self._error(503, "UPSTREAM_TIMEOUT",
                                                         "error.upstream_timeout",
                                                         "upstream trip_engine unavailable",
                                                         retryable=True,
                                                         details={"upstream": "trip_engine"}))
                        return
                    except _UpstreamError as exc:
                        self._send_json(504, self._error(504, "UPSTREAM_TIMEOUT",
                                                         "error.upstream_timeout", str(exc),
                                                         retryable=True))
                        return
                    self._send_json(200, self._success(data))
                    return

            self._send_json(404, self._error(404, "BAD_REQUEST", "error.bad_request", "not found"))

    return Handler
