"""offline_kit 的 HTTP 服务：依赖发现、注册表、令牌与离线包生成（C8/C9）。"""
from __future__ import annotations

import hmac
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .package import CAPACITY_MB, PACKAGE_VERSION, OfflinePackager
except ImportError:  # 单模块独立测试时按顶层模块导入
    from package import CAPACITY_MB, PACKAGE_VERSION, OfflinePackager

try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from contracts.runtime import registry as _registry
except Exception:  # noqa: BLE001
    _registry = None

OFFLINE_RE = re.compile(r"^/trips/([^/]+)/offline-package$")


class OfflineKitService:
    module_id = "offline_kit"
    dependencies = ["trip_engine", "route_adapter"]

    def __init__(self, config, data_dir, workspace_root, logger):
        self.config = config or {}
        self.data_dir = Path(data_dir)
        self.workspace_root = Path(workspace_root)
        self.logger = logger
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
        self.packager = OfflinePackager()
        from modules.offline_kit.place_translations import PlaceTranslationStore
        self.place_translations = PlaceTranslationStore(self.data_dir / 'place_translations.json')

    def start(self):
        if not _registry:
            raise RuntimeError("缺少 contracts.runtime.registry，无法注册端口")
        # 端口粘性：没有显式配置时复用上一次登记的端口，书签/深链在重启后依然有效
        port = _registry.resolve_port(self.config, self.module_id, self.workspace_root)
        _registry.check_no_live_instance(self.workspace_root, self.module_id)
        for dep in self.dependencies:
            self.upstreams[dep] = self._wait_for_upstream(dep, timeout=30.0)
        handler = _make_handler(self)
        try:
            self._httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as exc:
            raise RuntimeError(f"端口 {port or '自动'} 绑定失败：{exc}") from exc
        self.port = self._httpd.server_port
        _registry.write(_registry.build_registration(
            self.module_id, self.port, self.token, depends_on=self.dependencies,
            endpoints=["/health", "/trips/{id}/offline-package", "/place-names", "/place-names:confirm"]), self.workspace_root)
        self._http_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._http_thread.start()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._log(f"offline_kit 已启动：http://127.0.0.1:{self.port}")

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
        self._log("offline_kit 已停止")

    def _log(self, message):
        try:
            if hasattr(self.logger, "info"):
                self.logger.info(str(message))
            elif callable(self.logger):
                self.logger(str(message))
        except Exception:  # noqa: BLE001
            pass

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

    def health_payload(self):
        status = "degraded" if self.upstream_down else "ok"
        return {"module_id": self.module_id, "status": status, "contract_version": _registry.CONTRACT_VERSION,
                "ready": True, "started_at": self.started_at, "degraded": self.upstream_down,
                "degraded_reason": self.degraded_reason,
                "upstreams": {m: ("down" if self.upstream_down else "up") for m in self.upstream_ids}}

    def _call(self, module_id, method, path, payload=None):
        # 调用前先刷新，避免上游刚重启时请求撞上旧端口。
        # upstream_down 只是给 /health 的信号，能不能调通由这次调用本身决定。
        self._refresh_upstreams()
        reg = self.upstreams.get(module_id)
        if not reg:
            raise _UpstreamDown(module_id)
        try:
            return _registry.call_json(reg, method, path, payload)
        except _registry.RegistryError as exc:
            raise _UpstreamDown(module_id) from exc

    def _fetch_trip(self, trip_id):
        envelope = self._call("trip_engine", "GET", f"/trips/{trip_id}")
        if isinstance(envelope, dict) and envelope.get("ok") is True:
            return envelope.get("data") or {}
        if isinstance(envelope, dict) and "trip_id" in envelope:
            return envelope
        raise _UpstreamError("trip_engine 返回结构非法")

    def _station_provider(self, station_id):
        envelope = self._call("route_adapter", "GET", f"/stations/{station_id}")
        if isinstance(envelope, dict) and envelope.get("ok") is True:
            return envelope.get("data")
        return envelope

    @staticmethod
    def _place_point(point):
        if not isinstance(point,dict) or not isinstance(point.get('name_zh'),str) or not point['name_zh'].strip() or len(point['name_zh'])>200:
            raise ValueError('请提供有效地名')
        for key in ('city','type','place_id','station_id','poi_id','id','name_en','name_en_for_zh'):
            if key in point and point[key] is not None and (not isinstance(point[key],str) or len(point[key])>200):
                raise ValueError('地名字段必须是文本')
        if 'coordinate' in point and point['coordinate'] is not None and not isinstance(point['coordinate'],dict):
            raise ValueError('地点坐标格式不正确')
        return {k:v for k,v in point.items() if k in ('city','type','place_id','station_id','poi_id','id','coordinate','name_zh','name_en','name_en_for_zh')}

    def resolve_places(self,payload):
        points=payload.get('points')
        if not isinstance(points,list) or len(points)>1000:
            raise ValueError('地名批量请求最多 1000 个地点')
        resolver=self.place_translations.resolver()
        entries=[]
        for point in points:
            selected=self._place_point(point)
            entries.append({**resolver.resolve(selected),'point':selected})
        return {'entries':entries,'translation_version':resolver.version,'package_version':PACKAGE_VERSION}

    def confirm_place(self,payload):
        point=self._place_point(payload.get('point'))
        result=self.place_translations.confirm(point,payload.get('name_en'))
        return {'entry':{**result,'point':point},'translation_version':self.place_translations.resolver().version,'package_version':PACKAGE_VERSION}

    def generate(self, trip_id):
        trip = self._fetch_trip(trip_id)
        for day in trip.get('days') or []:
            for stop in day.get('ordered_stops') or []:
                route = stop.get('transit_from_previous') or {}
                destination=route.get('to') or {}
                if stop.get('poi_id') and destination.get('poi_id') and stop['poi_id']!=destination['poi_id']:
                    raise ValueError(f"Day {day['day_index']} 地点已更改，请重新计算交通后生成离线卡片")
                if any(stop.get(field) is None for field in ('arrival_at', 'departure_at')) or route.get('duration_seconds') is None:
                    raise ValueError(f"Day {day['day_index']} 停靠点 {stop.get('stop_id') or stop.get('stop_order')} 的时间轴未完成，请先计算交通并检查行程")
        payload = self.packager.build(trip, station_provider=self._station_provider, resolver=self.place_translations.resolver() if hasattr(self,'place_translations') else None)
        for day in payload['days']:
            if day['end_transfer_required'] and (day['end_transfer'] or {}).get('duration_seconds') is None:
                raise ValueError(f"Day {day['day_index']} 终点交通未完成，请先计算当天全部区间交通")
        # 体积上限 5MB（字体子集 <=1.5MB 计入，本实现不内嵌字体）
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size > CAPACITY_MB * 1024 * 1024:
            raise _UpstreamError("离线包超过 5MB 上限")
        return {"package_version": PACKAGE_VERSION, "trip_version": trip.get("version"),
                "generated_at": int(time.time()), "ttl_hours": self.packager.ttl_hours,
                "size_bytes": size, "payload": payload}


class _UpstreamDown(RuntimeError):
    pass


class _UpstreamError(RuntimeError):
    pass


def _fallback_token():
    import secrets
    return secrets.token_urlsafe(32)


def _make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "inboundroute-offline-kit/0.1"

        def log_message(self, fmt, *args):  # noqa: A003
            return

        def _json_body(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
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
            return {"ok": True, "data": data, "meta": {"version": _registry.CONTRACT_VERSION, "server_time": int(time.time())}}

        def _error(self, status, code, message_key, message, retryable=False, details=None):
            return {"ok": False, "error": {"code": code, "message_key": message_key, "message": message,
                                            "details": details or {}, "retryable": retryable,
                                            "trace_id": uuid.uuid4().hex}}

        def _check_token(self):
            if not hmac.compare_digest(self.headers.get("X-Module-Token", ""), service.token):
                self._send_json(403, self._error(403, "FORBIDDEN", "error.forbidden", "invalid module token"))
                return False
            return True

        def _path(self):
            p = self.path.split("?", 1)[0]
            if p.startswith("/api/v1"):
                p = p[len("/api/v1"):]
            return p or "/"

        def do_GET(self):  # noqa: N802
            if self._path() == "/health":
                self._send_json(200, service.health_payload())
                return
            if not self._check_token():
                return
            self._send_json(404, self._error(404, "BAD_REQUEST", "error.bad_request", "not found"))

        def do_POST(self):  # noqa: N802
            path = self._path()
            if not self._check_token():
                return
            if path in ('/place-names','/place-names:confirm'):
                try:
                    payload=self._json_body()
                    if not isinstance(payload,dict): raise ValueError('请求体必须为对象')
                    data=service.resolve_places(payload) if path=='/place-names' else service.confirm_place(payload)
                    self._send_json(200,self._success(data))
                except (ValueError,TypeError) as exc:
                    self._send_json(400,self._error(400,'BAD_REQUEST','error.bad_request',str(exc)))
                return
            m = OFFLINE_RE.match(path)
            if m:
                if service.upstream_down:
                    self._send_json(503, self._error(503, "UPSTREAM_TIMEOUT", "error.upstream_timeout",
                                                     "upstream unavailable", retryable=True))
                    return
                try:
                    data = service.generate(m.group(1))
                except ValueError as exc:
                    self._send_json(400, self._error(400, "BAD_REQUEST", "error.bad_request", str(exc)))
                    return
                except _UpstreamDown:
                    self._send_json(503, self._error(503, "UPSTREAM_TIMEOUT", "error.upstream_timeout",
                                                     "upstream unavailable", retryable=True))
                    return
                except _UpstreamError as exc:
                    self._send_json(500, self._error(500, "INTERNAL", "error.internal", str(exc), retryable=True))
                    return
                self._send_json(200, self._success(data))
                return
            self._send_json(404, self._error(404, "BAD_REQUEST", "error.bad_request", "not found"))

    return Handler
