"""行程 HTTP 适配：令牌鉴权、请求路由、响应信封与服务器生命周期。"""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .errors import EngineError
from .service import TripService
from .domain import (
    MAX_BODY,
    MODULE_ID,
    now_seconds,
)


def build_handler(service: TripService, token: str):
    """按契约把服务包装成 HTTP handler；token 用于除 /health 外的所有请求。"""

    class Handler(BaseHTTPRequestHandler):
        server_version = "trip_engine/0.1"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *_):
            pass

        # -------------------------------------------------- 响应与鉴权

        def reply(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def ok(self, data, status=200, meta=None):
            envelope = {"ok": True, "data": data,
                        "meta": {"contract_version": service.contract_version,
                                 "server_time": now_seconds(), **(meta or {})}}
            self.reply(status, envelope)

        def fail(self, status, code, message, details=None):
            self.reply(status, {"ok": False, "error": {"code": code, "message": message,
                                                       "details": details or {}, "retryable": status >= 500}})

        def _host_allowed(self) -> bool:
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in allowed

        def _authorized(self) -> bool:
            if not self._host_allowed():
                return False
            return secrets.compare_digest(self.headers.get("X-Module-Token", ""), token)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                raise EngineError(413, "BAD_REQUEST", f"请求体超过 {MAX_BODY} 字节")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EngineError(400, "BAD_REQUEST", f"请求体必须是 JSON：{exc}") from exc

        def _dispatch(self, method):
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            if path == "/health":
                return self.ok({"module_id": MODULE_ID, "status": "ok", "ready": True,
                                "contract_version": service.contract_version,
                                "contract_version": service.contract_version,
                                "poi_source": service.store.poi_source,
                                "trips": len(service.store.list_trips())})
            if not self._authorized():
                return self.fail(403, "FORBIDDEN", "缺少或错误的 X-Module-Token")
            parts = [segment for segment in path.strip("/").split("/") if segment]
            try:
                return self._route(method, parts, query)
            except EngineError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)
            except (ValueError, OSError, RuntimeError) as exc:
                return self.fail(400, "BAD_REQUEST", str(exc))

        def _route(self, method, parts, query):
            if parts == ["trips:preview"] and method == "POST":
                return self.ok(service.preview_trip(self._body()))
            if parts == ["trips:recommended"] and method == "POST":
                return self.ok(service.create_recommended_trip(self._body()), status=201)
            if (len(parts) == 3 and parts[0] == "trips"
                    and parts[2] == "recommendations:apply" and method == "POST"):
                return self.ok(service.apply_recommendations(
                    parts[1], self._body(), self.headers.get("If-Match")))
            if parts == ["trips:validate"] and method == "POST":
                # 只校验不落盘：工作台在真正创建前先打这个接口。
                return self.ok(service.validate_trip(self._body()))
            if parts == ["trips"] and method == "POST":
                return self.ok(service.create_trip(self._body()), status=201)
            if parts == ["trips"] and method == "GET":
                ids = service.store.list_trips()
                trips = []
                for trip_id in ids:
                    try:
                        trip = service.get_trip(trip_id)
                        trips.append({"trip_id": trip_id, "version": trip["version"],
                                      "start_date": trip["days"][0]["date"], "duration_days": len(trip["days"]),
                                      "updated_at": trip.get("updated_at", 0)})
                    except (EngineError, KeyError, IndexError):
                        continue
                trips.sort(key=lambda item: item["updated_at"], reverse=True)
                return self.ok({"trip_ids": ids, "trips": trips})
            if parts == ["pois"] and method == "GET":
                return self.ok(service.list_pois(query))
            if parts == ["anchors"] and method == "GET":
                return self.ok(service.list_anchors(query))
            if len(parts) == 2 and parts[0] == "pois" and method == "GET":
                return self.ok(service.get_poi(parts[1]))
            if len(parts) >= 2 and parts[0] == "trips":
                trip_id = parts[1]
                if len(parts) == 2 and method == "GET":
                    return self.ok(service.get_trip(trip_id))
                if len(parts) == 2 and method == "PATCH":
                    return self.ok(service.patch_trip(trip_id, self._body(), self.headers.get("If-Match")))
                if len(parts) == 2 and method == "DELETE":
                    return self.ok(service.delete_trip(trip_id))
                if len(parts) == 2 and parts[1].endswith(":duplicate") and method == "POST":
                    return self.ok(service.duplicate_trip(parts[1][: -len(":duplicate")]), status=201)
                if len(parts) == 5 and parts[2] == "days" and parts[4] == "stops":
                    if method == "POST":
                        return self.ok(service.add_stop(trip_id, parts[3], self._body()), status=201)
                    if method == "PUT":
                        return self.ok(service.reorder_stops(trip_id, parts[3], self._body()))
                if len(parts) == 6 and parts[2] == "days" and parts[4] == "stops" and method == "DELETE":
                    return self.ok(service.remove_stop(trip_id, parts[3], parts[5]))
                if len(parts) == 6 and parts[2] == "days" and parts[4] == "stops" and parts[5] == "evening" and method == "POST":
                    return self.ok(service.move_stop_to_evening(trip_id, parts[3], self._body().get("poi_id", "")))
                if (len(parts) == 7 and parts[2] == "days" and parts[4] == "stops"
                        and parts[6] == "move" and method == "POST"):
                    return self.ok(service.move_stop(trip_id, parts[3], parts[5], self._body()))
            raise EngineError(404, "BAD_REQUEST", f"操作不存在：{method} /{'/'.join(parts)}")

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        def do_PATCH(self):
            self._dispatch("PATCH")

        def do_DELETE(self):
            self._dispatch("DELETE")

    return Handler


def build_server(service: TripService, token: str, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """创建（未启动）HTTP 服务；测试与宿主插件共用。"""
    server = ThreadingHTTPServer((host, port), build_handler(service, token))
    server.daemon_threads = True
    return server


def serve(service: TripService, token: str, port: int, host: str, stop_event) -> None:
    """后台线程内 serve_forever，stop_event 置位或超时后收尾。"""
    server = build_server(service, token, port, host)
    service.port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        server.shutdown()
        server.server_close()
