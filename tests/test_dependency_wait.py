"""启动期依赖等待：必须能跟上 trip_engine 重启后的新端口。

真实故障（logs/rules_engine.log）：
    2026-09-29 22:52:33  等待上游 trip_engine 就绪：http://127.0.0.1:53559
    2026-09-29 22:53:04  启动失败：依赖 trip_engine 在 30s 内未就绪（未收到响应）
而同一时刻 `data/_registry/trip_engine.json` 写的是 53182。

原因：上一轮运行残留的注册文件指向已经死掉的端口，而 `wait_for_dependency()` 把 base_url
固定在「第一次读到的值」上，等待期间从不重读注册表，于是新实例换了端口它也不知道。
更糟的是 rules_engine 之后还会一直用那个死地址，`_require_client()` 永远失败。

这个文件钉住三件事：
    1. 等待期间注册文件被改写（换端口）→ 必须采用新端口并成功返回；
    2. 注册文件暂时不存在（启动竞态）→ 必须继续等，而不是立刻抛「未运行」；
    3. 等不到时仍要抛错，且错误信息要能指导用户（不静默降级）。
另外验证 rules_engine 的客户端会跟随重新注册的上游，而不是抱着旧端口不放。
"""
import http.server
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "contracts")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from contracts.runtime import registry  # noqa: E402

MODULE_DIR = ROOT / "modules" / "rules_engine"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
from client import TripEngineClient  # noqa: E402


class FakeUpstream:
    """一个只会 /health 的最小 HTTP 服务，可记录收到的令牌。"""

    def __init__(self, status="ok", ready=True, trip=None):
        self.payload = {"module_id": "trip_engine", "status": status, "ready": ready}
        self.trip = trip or {"trip_id": "trip_1", "version": 1, "days": []}
        self.tokens = []
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _send(self, body):
                raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                outer.requests.append(self.path)
                if self.path == "/health":
                    return self._send(outer.payload)
                outer.tokens.append(self.headers.get("X-Module-Token"))
                return self._send({"ok": True, "data": outer.trip})

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class DependencyWaitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.stop()
        self.temp.cleanup()

    def live_upstream(self, **kwargs):
        server = FakeUpstream(**kwargs)
        self.servers.append(server)
        return server

    def register(self, base_url, token="tok-old"):
        port = int(base_url.rsplit(":", 1)[1])
        registry.write(registry.build_registration("trip_engine", port, token), self.root)

    # ------------------------------------------------------------ 1. 换端口

    def test_stale_registration_is_replaced_while_waiting(self):
        """上一轮残留的注册文件指向死端口，新实例稍后换端口注册 —— 必须跟上。"""
        self.register("http://127.0.0.1:9", token="tok-stale")     # 9 端口必然连不上
        live = self.live_upstream()
        threading.Timer(0.4, lambda: self.register(live.base_url, token="tok-new")).start()

        registration, health = registry.wait_for_registration(self.root, "trip_engine", timeout=15.0)

        self.assertEqual(registration.port, live.httpd.server_port)
        self.assertEqual(registration.token, "tok-new")
        self.assertEqual(health.get("status"), "ok")

    # ------------------------------------------------------------ 2. 还没有注册文件

    def test_missing_registration_waits_instead_of_failing_fast(self):
        """launcher 并发启动时，依赖方常先于被依赖方启动：应继续等，而不是立刻报「未运行」。"""
        live = self.live_upstream()
        threading.Timer(0.4, lambda: self.register(live.base_url, token="tok-new")).start()

        registration, _ = registry.wait_for_registration(self.root, "trip_engine", timeout=15.0)
        self.assertEqual(registration.port, live.httpd.server_port)

    # ------------------------------------------------------------ 3. 仍要显式失败

    def test_timeout_still_raises_with_actionable_message(self):
        self.register("http://127.0.0.1:9", token="tok-stale")
        with self.assertRaises(registry.RegistryError) as raised:
            registry.wait_for_registration(self.root, "trip_engine", timeout=1.0,
                                           initial_interval=0.05, max_interval=0.1)
        message = str(raised.exception)
        self.assertIn("trip_engine", message)
        self.assertIn("管理页面", message)

    def test_not_ready_yet_keeps_waiting(self):
        """依赖已响应但 ready=false 时不算就绪。"""
        starting = self.live_upstream(status="starting", ready=False)
        self.register(starting.base_url)
        threading.Timer(0.4, lambda: setattr(starting, "payload",
                                             {"module_id": "trip_engine", "status": "ok", "ready": True})).start()
        registration, health = registry.wait_for_registration(self.root, "trip_engine", timeout=15.0)
        self.assertEqual(health.get("status"), "ok")
        self.assertEqual(registration.port, starting.httpd.server_port)

    # ------------------------------------------------------------ 4. 客户端跟随重启

    def test_client_follows_reregistered_upstream(self):
        """trip_engine 重启会换端口和令牌，客户端不能继续打旧地址。"""
        first = self.live_upstream()
        self.register(first.base_url, token="tok-first")
        client = TripEngineClient(first.base_url, "tok-first",
                                  resolver=lambda: registry.try_read(self.root, "trip_engine"))

        self.assertEqual(client.get_trip("trip_1")["trip_id"], "trip_1")
        self.assertEqual(first.tokens, ["tok-first"])

        second = self.live_upstream()
        self.register(second.base_url, token="tok-second")
        self.assertEqual(client.get_trip("trip_1")["trip_id"], "trip_1")
        self.assertEqual(second.tokens, ["tok-second"], "应使用重新注册后的新地址与新令牌")

    def test_client_without_resolver_keeps_old_behaviour(self):
        live = self.live_upstream()
        client = TripEngineClient(live.base_url, "tok-direct")
        self.assertEqual(client.get_trip("trip_1")["trip_id"], "trip_1")
        self.assertEqual(live.tokens, ["tok-direct"])

    # ------------------------------------------------------------ 5. 常驻服务跟随上游重启

    def test_route_adapter_follows_restarted_trip_engine(self):
        """route_adapter 长期驻留，上游换端口后必须自己跟过去。

        改之前它把启动那一刻的 Registration 快照一直用下去：trip_engine 一重启，
        它就会永远对着死端口，`/health` 永久 degraded、业务端点永久 503
        ——现象是「上游明明在跑，却一直说不可用」。
        """
        from modules.route_adapter.service import RouteAdapterService  # 延迟导入，避免影响其它用例

        first = self.live_upstream()
        self.register(first.base_url, token="tok-first")
        service = RouteAdapterService({"provider": "mock"}, self.root / "route", self.root,
                                       lambda _: None, ROOT / "modules" / "route_adapter")
        self.addCleanup(service.stop)
        service.start()
        try:
            self.assertEqual(service._call_trip_engine("GET", "/trips/trip_1")["data"]["trip_id"], "trip_1")
            self.assertEqual(first.tokens, ["tok-first"])

            # 上游重启：换端口、换令牌
            second = self.live_upstream()
            self.register(second.base_url, token="tok-second")
            service._refresh_upstreams()

            self.assertEqual(service.upstreams["trip_engine"].port, second.httpd.server_port)
            self.assertEqual(service._call_trip_engine("GET", "/trips/trip_1")["data"]["trip_id"], "trip_1")
            self.assertEqual(second.tokens, ["tok-second"])
            self.assertEqual(first.tokens, ["tok-first"], "不应该再打已经停掉的那个实例")
        finally:
            service.stop()

    def test_offline_kit_refreshes_upstreams_too(self):
        """offline_kit 是同一份写法的另一处：注册表刷新必须同样生效。"""
        from modules.offline_kit.service import OfflineKitService

        first = self.live_upstream()
        self.register(first.base_url, token="tok-first")
        service = OfflineKitService({}, self.root / "offline", self.root, lambda _: None)
        service.upstreams["trip_engine"] = registry.read(self.root, "trip_engine")

        second = self.live_upstream()
        self.register(second.base_url, token="tok-second")
        service._refresh_upstreams()

        self.assertEqual(service.upstreams["trip_engine"].port, second.httpd.server_port)
        self.assertEqual(service.upstreams["trip_engine"].token, "tok-second")

    def test_refresh_drops_and_restores_registrations(self):
        """注册文件消失要能被发现（上游停了），重新出现也能再被拿到。"""
        live = self.live_upstream()
        self.register(live.base_url)
        self.assertEqual(registry.refresh(self.root, ["trip_engine"])["trip_engine"].port,
                         live.httpd.server_port)

        registry.remove(self.root, "trip_engine")
        self.assertIsNone(registry.refresh(self.root, ["trip_engine"])["trip_engine"])

        self.register(live.base_url)
        self.assertEqual(registry.refresh(self.root, ["trip_engine"])["trip_engine"].port,
                         live.httpd.server_port)


if __name__ == "__main__":
    unittest.main()
