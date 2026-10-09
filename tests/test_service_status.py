"""R-4：管理页面展示服务型模块的端口与 /health 状态。

覆盖点：service 元信息解析、两个注册文件位置的读取、健康探测的四种结果、
探测缓存、以及清单/注册文件异常时不崩。
"""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.manager import Manager

PLUGIN = '''
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404); self.end_headers(); return
        body = json.dumps({"module_id": "svc_engine", "status": "ok", "ready": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

def run(context):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    (context.data_dir / "registry.json").write_text(
        json.dumps({"module_id": "svc_engine", "port": port,
                    "base_url": f"http://127.0.0.1:{port}"}), encoding="utf-8")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    while not context.wait(1):
        pass
    server.shutdown()
'''

PLAIN_PLUGIN = "def run(context):\n    while not context.wait(1):\n        pass\n"


def write_module(root: Path, module_id: str, manifest: dict, code: str) -> Path:
    folder = root / "modules" / module_id
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (folder / "plugin.py").write_text(code, encoding="utf-8")
    return folder


class ServiceStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service_manifest = {
            "id": "svc_engine", "name": "服务模块", "version": "0.1.0", "description": "验证端口与健康状态",
            "dependencies": [],
            "service": {"enabled": True, "health_path": "/health", "open_path": "/", "title": "验证服务"},
        }
        write_module(self.root, "svc_engine", self.service_manifest, PLUGIN)
        write_module(self.root, "plain_mod",
                     {"id": "plain_mod", "name": "普通模块", "version": "0.1.0",
                      "description": "非服务模块", "dependencies": []}, PLAIN_PLUGIN)
        self.manager = Manager(self.root)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def card(self, module_id):
        return next(item for item in self.manager.list() if item["id"] == module_id)

    def test_service_metadata_and_plain_module(self):
        service = self.card("svc_engine")["service"]
        self.assertIsNotNone(service)
        self.assertEqual(service["health_path"], "/health")
        self.assertEqual(service["open_path"], "/")
        self.assertEqual(service["health"], "no_port")
        self.assertIsNone(self.card("plain_mod")["service"])

    def test_running_service_reports_port_and_health(self):
        self.manager.enable("svc_engine")
        self.manager.start("svc_engine")
        deadline = time.monotonic() + 10
        service = self.card("svc_engine")["service"]
        while time.monotonic() < deadline and service["health"] != "ok":
            time.sleep(0.3)
            service = self.card("svc_engine")["service"]
        self.assertEqual(service["health"], "ok")
        self.assertIsInstance(service["port"], int)
        self.assertTrue(service["base_url"].startswith("http://127.0.0.1:"))
        self.assertIn(service["detail"], ("/health 通过",))

    def test_health_result_is_cached(self):
        self.manager.enable("svc_engine")
        self.manager.start("svc_engine")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self.card("svc_engine")["service"]["health"] != "ok":
            time.sleep(0.3)
        started = time.monotonic()
        for _ in range(5):
            self.manager.list()
        self.assertLess(time.monotonic() - started, 1.0)

    def test_registered_but_dead_service_reports_down(self):
        self.manager.stop("svc_engine")
        registry = self.root / "data" / "_registry" / "svc_engine.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"module_id": "svc_engine", "port": 59999,
                                        "base_url": "http://127.0.0.1:59999"}), encoding="utf-8")
        service = self.card("svc_engine")["service"]
        self.assertEqual(service["health"], "down")
        self.assertEqual(service["port"], 59999)

    def test_broken_registry_does_not_break_page(self):
        for candidate in (self.root / "data" / "_registry" / "svc_engine.json",
                          self.root / "data" / "svc_engine" / "registry.json"):
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text("{ 坏 json", encoding="utf-8")
        self.manager._health_cache.clear()
        self.assertEqual(self.card("svc_engine")["service"]["health"], "no_port")

    def test_service_disabled_or_malformed_is_not_a_service(self):
        folder = self.root / "modules" / "svc_engine"
        for service in ({"enabled": False}, "yes", None, {"enabled": True, "health_path": "no-slash"}):
            manifest = dict(self.service_manifest, service=service)
            (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            service_info = self.card("svc_engine")["service"]
            if service is None or service == {"enabled": False} or service == "yes":
                self.assertIsNone(service_info, service)
            else:
                # health_path 非法时回落到 /health，而不是崩掉
                self.assertEqual(service_info["health_path"], "/health")


if __name__ == "__main__":
    unittest.main()
