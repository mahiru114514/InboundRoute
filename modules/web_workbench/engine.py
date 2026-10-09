"""行程工作台（web_workbench）的 HTTP 服务：静态前端 + 到各引擎的代理。

职责边界（contracts/MODULE_RUNTIME.md §4）：
    · 它是**唯一可以代表用户调用其他模块**的模块；
    · 浏览器不接触任何引擎令牌——令牌只留在本进程内存里，代理请求时注入；
    · 依赖未就绪时不报错崩掉，而是把状态交给前端展示（演示需要能看出「哪一块没起来」）。
"""
from __future__ import annotations

import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

try:
    from .proxy import ServiceRegistry, UpstreamError
except ImportError:  # pragma: no cover
    from proxy import ServiceRegistry, UpstreamError  # type: ignore

try:
    from .map_config import build_csp, map_config
except ImportError:  # 兼容旧脚本入口
    from modules.web_workbench.map_config import build_csp, map_config

try:
    from .currency_rates import CurrencyRates, CurrencyRateError
except ImportError:  # 兼容旧脚本入口
    from modules.web_workbench.currency_rates import CurrencyRates, CurrencyRateError

MODULE_ID = "web_workbench"
CONTRACT_VERSION = "0.3.3"
WEB_DIR = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/place_names.js": ("place_names.js", "text/javascript; charset=utf-8"),
    "/common_i18n_catalog.js": ("common_i18n_catalog.js", "text/javascript; charset=utf-8"),
    "/common_i18n_patterns.js": ("common_i18n_patterns.js", "text/javascript; charset=utf-8"),
    "/poi_i18n_catalog.js": ("poi_i18n_catalog.js", "text/javascript; charset=utf-8"),
    "/suggestions_i18n.js": ("suggestions_i18n.js", "text/javascript; charset=utf-8"),
    "/onboarding_content.js": ("onboarding_content.js", "text/javascript; charset=utf-8"),
    "/onboarding.js": ("onboarding.js", "text/javascript; charset=utf-8"),
    "/offline_view.js": ("offline_view.js", "text/javascript; charset=utf-8"),
    "/i18n_catalog.js": ("i18n_catalog.js", "text/javascript; charset=utf-8"),
    "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
    "/poi_content.js": ("poi_content.js", "text/javascript; charset=utf-8"),
    "/recommendations.js": ("recommendations.js", "text/javascript; charset=utf-8"),
    "/map_view.js": ("map_view.js", "text/javascript; charset=utf-8"),
    "/poi_list.js": ("poi_list.js", "text/javascript; charset=utf-8"),
    "/itinerary.js": ("itinerary.js", "text/javascript; charset=utf-8"),
    "/setup.js": ("setup.js", "text/javascript; charset=utf-8"),
    "/anchors.js": ("anchors.js", "text/javascript; charset=utf-8"),
    "/services.js": ("services.js", "text/javascript; charset=utf-8"),
    "/poi_details.js": ("poi_details.js", "text/javascript; charset=utf-8"),
    "/runtime.js": ("runtime.js", "text/javascript; charset=utf-8"),
    "/budget_assessment.js": ("budget_assessment.js", "text/javascript; charset=utf-8"),
    "/currency.js": ("currency.js", "text/javascript; charset=utf-8"),
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/day_cards.js": ("day_cards.js", "text/javascript; charset=utf-8"),
    "/day_points.js": ("day_points.js", "text/javascript; charset=utf-8"),
    "/navigation.js": ("navigation.js", "text/javascript; charset=utf-8"),
    "/reminders.js": ("reminders.js", "text/javascript; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/map.js": ("map.js", "text/javascript; charset=utf-8"),
    "/flow.js": ("flow.js", "text/javascript; charset=utf-8"),
    "/offline_cache.js": ("../../offline_kit/web/offline_cache.js", "text/javascript; charset=utf-8"),
}
MAX_BODY = 1024 * 1024
SESSION_PATH = "/api/session"


def build_handler(services: ServiceRegistry, token: str, maps: dict, currency_rates=None):
    csp = build_csp(maps)
    rates = currency_rates if currency_rates is not None else CurrencyRates()

    class Handler(BaseHTTPRequestHandler):
        server_version = "web_workbench/0.1"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def log_message(self, *_):
            pass

        # -------------------------------------------------- 基础响应

        def reply(self, status, payload, content_type="application/json; charset=utf-8"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(body)

        def ok(self, data, status=200):
            self.reply(status, {"ok": True, "data": data,
                                "meta": {"contract_version": CONTRACT_VERSION}})

        def fail(self, status, code, message, details=None):
            self.reply(status, {"ok": False, "error": {"code": code, "message": message,
                                                       "details": details or {}}})

        def _host_allowed(self) -> bool:
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in allowed

        def _authorized(self) -> bool:
            return self._host_allowed() and secrets.compare_digest(
                self.headers.get("X-Workbench-Token", ""), token)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                raise UpstreamError(413, "BAD_REQUEST", f"请求体超过 {MAX_BODY} 字节")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UpstreamError(400, "BAD_REQUEST", f"请求体必须是 JSON：{exc}") from exc

        # -------------------------------------------------- 路由

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self._host_allowed():
                return self.fail(403, "FORBIDDEN", "仅允许本机访问")
            if path in ASSETS:
                filename, mime = ASSETS[path]
                return self.reply(200, (WEB_DIR / filename).read_bytes(), mime)
            if path == SESSION_PATH:
                # 页面加载时取会话令牌与地图配置（CSP 禁止内联脚本，所以不走注入 HTML 的路子）。
                return self.ok({"token": token,
                                "base": f"http://127.0.0.1:{self.server.server_port}",
                                "map": maps})
            if path == "/health":
                snapshot = services.snapshot()
                degraded = [item["module_id"] for item in snapshot["services"] if not item["ready"]]
                return self.ok({"module_id": MODULE_ID, "status": "ok", "ready": True,
                                "degraded": bool(degraded), "degraded_reason": ",".join(degraded) or None})
            if not self._authorized():
                return self.fail(403, "FORBIDDEN", "请求校验失败，请刷新页面")
            try:
                if path == "/api/services":
                    return self.ok(services.snapshot())
                if path == "/api/currency-rates":
                    query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    if (set(query) - {'currency', 'refresh'} or len(query.get('currency', [])) != 1
                            or len(query.get('refresh', ['0'])) != 1
                            or query.get('refresh', ['0'])[0] not in ('0', '1')):
                        return self.fail(400, 'BAD_REQUEST', '汇率请求需要一个有效 currency，可选 refresh=1')
                    return self.ok(rates.get(query['currency'][0], refresh=query.get('refresh', ['0'])[0] == '1'))
                if path == "/api/pois":
                    return self.ok(services.call("trip_engine", "GET", "/pois"))
                if path.startswith("/api/pois/"):
                    return self.ok(services.call("trip_engine", "GET", path[len("/api"):]))
                if path == "/api/anchors":
                    # 抵达/离境口岸与住宿候选由 trip_engine 统一供给（原来写死在前端 app.js）。
                    return self.ok(services.call("trip_engine", "GET", "/anchors"))
                if path == "/api/trips":
                    return self.ok(services.call("trip_engine", "GET", "/trips"))
                if path.startswith("/api/trips/"):
                    return self.ok(services.call("trip_engine", "GET", path[len("/api"):]))
                return self.fail(404, "NOT_FOUND", f"页面或接口不存在：{path}")
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)
            except CurrencyRateError as exc:
                return self.fail(exc.status, exc.code, str(exc))

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self._host_allowed():
                return self.fail(403, "FORBIDDEN", "仅允许本机访问")
            try:
                if not self._authorized():
                    self._body()  # 消费请求体，避免 Windows 连接重置
                    return self.fail(403, "FORBIDDEN", "请求校验失败，请刷新页面")
                payload = self._body()
                if path in ('/api/place-names','/api/place-names:confirm'):
                    return self.ok(services.call('offline_kit','POST',path[len('/api'):],payload))
                if path == "/api/recommendations:generate":
                    return self.ok(services.call(
                        "recommendation_engine", "POST", "/recommendations:generate", payload))
                if path == "/api/trips:preview":
                    return self.ok(services.call("trip_engine", "POST", "/trips:preview", payload))
                if path == "/api/trips:recommended":
                    return self.ok(services.call(
                        "trip_engine", "POST", "/trips:recommended", payload), status=201)
                if re.fullmatch(r"/api/trips/[^/]+/recommendations:apply", path):
                    version = self.headers.get("If-Match")
                    return self.ok(services.call("trip_engine", "POST", path[len("/api"):], payload,
                        headers={"If-Match": version} if version else None))
                if path == "/api/trips:validate":
                    # 只校验不落盘：页面在真正创建前先跑一次，避免「先建了才发现不合法」。
                    return self.ok(services.call("trip_engine", "POST", "/trips:validate", payload))
                if path == "/api/trips":
                    return self.ok(services.call("trip_engine", "POST", "/trips", payload), status=201)
                if re.fullmatch(r"/api/trips/[^/]+:duplicate", path):
                    return self.ok(services.call("trip_engine", "POST", path[len("/api"):], payload), status=201)
                if re.fullmatch(r"/api/trips/[^/]+/(rules:evaluate|rules:precheck|conflicts/[^/]+/confirm)", path):
                    return self.ok(services.call("rules_engine", "POST", path[len("/api"):], payload))
                if re.fullmatch(r"/api/trips/[^/]+/days/[0-9]+/routes:compute", path):
                    return self.ok(services.call("route_adapter", "POST", path[len("/api"):], payload))
                if re.fullmatch(r"/api/trips/[^/]+/offline-package", path):
                    return self.ok(services.call("offline_kit", "POST", path[len("/api"):], payload))
                if path.startswith("/api/trips/"):
                    return self.ok(services.call("trip_engine", "POST", path[len("/api"):], payload))
                return self.fail(404, "NOT_FOUND", f"接口不存在：{path}")
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)

        def do_PATCH(self):
            path = urlsplit(self.path).path
            if not self._host_allowed():
                return self.fail(403, "FORBIDDEN", "仅允许本机访问")
            try:
                if not self._authorized():
                    self._body()
                    return self.fail(403, "FORBIDDEN", "请求校验失败，请刷新页面")
                payload = self._body()
                if path.startswith("/api/trips/"):
                    version = self.headers.get("If-Match")
                    return self.ok(services.call("trip_engine", "PATCH", path[len("/api"):], payload,
                                                 headers={"If-Match": version} if version else None))
                return self.fail(404, "NOT_FOUND", f"接口不存在：{path}")
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)

        def do_PUT(self):
            if not self._authorized():
                return self.fail(403, "FORBIDDEN", "请求校验失败，请刷新页面")
            try:
                path = urlsplit(self.path).path
                payload = self._body()
                if re.fullmatch(r"/api/trips/[^/]+/days/[0-9]+/stops", path):
                    return self.ok(services.call("trip_engine", "PUT", path[len("/api"):], payload))
                return self.fail(404, "NOT_FOUND", "操作不存在")
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)

        def do_DELETE(self):
            path = urlsplit(self.path).path
            if not self._host_allowed():
                return self.fail(403, "FORBIDDEN", "仅允许本机访问")
            if not self._authorized():
                return self.fail(403, "FORBIDDEN", "请求校验失败，请刷新页面")
            try:
                if path.startswith("/api/trips/"):
                    return self.ok(services.call("trip_engine", "DELETE", path[len("/api"):]))
                return self.fail(404, "NOT_FOUND", f"接口不存在：{path}")
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)

    return Handler


def build_server(services: ServiceRegistry, token: str, port: int = 0, host: str = "127.0.0.1",
                 maps: dict | None = None, currency_rates=None):
    server = ThreadingHTTPServer((host, port), build_handler(services, token, maps or {"ready": False}, currency_rates))
    server.daemon_threads = True
    return server


def serve(services: ServiceRegistry, token: str, port: int, host: str, stop_event, maps: dict | None = None) -> None:
    server = build_server(services, token, port, host, maps)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        server.shutdown()
        server.server_close()
