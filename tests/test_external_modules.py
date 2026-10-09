"""「模块到底在不在运行」的判定：不能只看「是不是本进程启动的」。

背景（真实故障）：
    `start_software.py --all` 拉起的模块是**另一个进程**的子进程。管理台（`manager.py` /
    `start.bat`）只认识自己 spawn 过的进程，于是把这些正在运行的模块显示成「未运行」，
    用户就去点「运行」，接着撞上模块自己的「检测到另一个运行实例」而失败 ——
    表现就是「明明 --all 起过了，还要一个个手动启动」。
"""
import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "modules" / "trip_engine")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from core.manager import Manager  # noqa: E402

MANIFEST = {
    "id": "trip_engine", "name": "行程引擎", "version": "1.0.0", "dependencies": [],
    "service": {"enabled": True, "health_path": "/health"},
}


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class HealthHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_GET(self):
        body = json.dumps({"ok": True, "data": {"status": "ok", "ready": True}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def dead_pid():
    """拿一个确定已经退出的 pid（不能用不存在的数字去猜，可能撞上真实进程）。"""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class ExternalModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "modules" / "trip_engine").mkdir(parents=True)
        (self.root / "modules" / "trip_engine" / "manifest.json").write_text(
            json.dumps(MANIFEST), encoding="utf-8")
        (self.root / "modules" / "trip_engine" / "plugin.py").write_text(
            "def run(ctx):\n    pass\n", encoding="utf-8")
        (self.root / "data" / "_registry").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_registration(self, port, pid):
        payload = {"module_id": "trip_engine", "port": port,
                   "base_url": f"http://127.0.0.1:{port}", "token": "t" * 32, "pid": pid,
                   "contract_version": "0.3.2", "started_at": 1791819600,
                   "depends_on": [], "endpoints": ["/health"]}
        path = self.root / "data" / "_registry" / "trip_engine.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def card(self):
        manager = Manager(self.root)
        try:
            return next(item for item in manager.list() if item["id"] == "trip_engine")
        finally:
            manager.close()

    def test_running_instance_from_another_process_is_reported_running(self):
        """别的进程拉起的实例：/health 通 → 必须显示「运行中」，并标出是外部实例。"""
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        port = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.write_registration(port, 12345)
            card = self.card()
            self.assertEqual(card["status"], "running")
            self.assertTrue(card["external"])
            self.assertEqual(card["service"]["health"], "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_start_refuses_to_duplicate_a_running_instance(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        port = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.write_registration(port, 12345)
            manager = Manager(self.root)
            try:
                manager.enable("trip_engine")
                with self.assertRaises(ValueError) as caught:
                    manager.start("trip_engine")
                self.assertIn("已经在运行", str(caught.exception))
                self.assertIn("Ctrl+C", str(caught.exception))     # 必须告诉用户去哪儿停
            finally:
                manager.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_can_start_module_with_external_dependency(self):
        folder = self.root / 'modules' / 'rules_engine'
        folder.mkdir()
        (folder / 'manifest.json').write_text(json.dumps({
            'id': 'rules_engine', 'name': '规则', 'version': '1',
            'dependencies': ['trip_engine']}), encoding='utf-8')
        (folder / 'plugin.py').write_text('def run(ctx):\n    ctx.wait(30)\n', encoding='utf-8')
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = Manager(self.root)
        try:
            self.write_registration(server.server_port, 12345)
            manager.enable('trip_engine')
            manager.enable('rules_engine')
            manager.start('rules_engine')
            card = next(item for item in manager.list() if item['id'] == 'rules_engine')
            self.assertEqual(card['status'], 'running')
            self.assertEqual(card['warning'], '')
        finally:
            manager.close()
            server.shutdown()
            server.server_close()

    def test_external_instance_cannot_be_configured_or_uninstalled(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        manager = Manager(self.root)
        try:
            self.write_registration(server.server_port, 12345)
            with self.assertRaisesRegex(ValueError, '停止'):
                manager.configure('trip_engine', {'port': 1234})
            with self.assertRaisesRegex(ValueError, '禁用'):
                manager.uninstall('trip_engine')
        finally:
            manager.close()
            server.shutdown()
            server.server_close()

    def test_stop_refuses_loudly_instead_of_silently_doing_nothing(self):
        """外部实例停不掉：必须报错，不能静默成功让用户以为停了。"""
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
        port = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.write_registration(port, 12345)
            manager = Manager(self.root)
            try:
                with self.assertRaises(ValueError) as caught:
                    manager.stop("trip_engine")
                self.assertIn("停不掉", str(caught.exception))
            finally:
                manager.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_stale_registration_with_dead_pid_is_not_reported_running(self):
        """残留注册文件 + 已死进程 + 没人监听：绝不能误报成「运行中」。"""
        self.write_registration(free_port(), dead_pid())
        card = self.card()
        self.assertFalse(card["external"])
        self.assertNotEqual(card["status"], "running")

    def test_registration_pid_alone_does_not_count_as_running(self):
        """只看 pid 会把「pid 被系统复用」误判成运行中，从而挡住用户启动模块。

        所以服务型模块必须有 /health 才算在跑；这里给一个「pid 活着但没人服务」的注册文件，
        要求判定为**不在运行**。
        """
        self.write_registration(free_port(), os.getpid())      # pid 活着，但那个端口没人监听
        card = self.card()
        self.assertFalse(card["external"])
        self.assertEqual(card["status"], "stopped")

    def test_service_run_marker_cannot_override_failed_health(self):
        """服务退出后 pid 被浏览器复用：残留 .run 不能覆盖 /health 失败。"""
        self.write_registration(free_port(), os.getpid())
        marker = self.root / "data" / "_registry" / "trip_engine.run"
        marker.write_text(json.dumps({"module_id": "trip_engine", "pid": os.getpid()}), encoding="utf-8")
        manager = Manager(self.root)
        try:
            card = next(item for item in manager.list() if item["id"] == "trip_engine")
            self.assertEqual(card["service"]["health"], "down")
            self.assertFalse(card["external"])
            self.assertEqual(card["status"], "stopped")
            self.assertFalse(manager._active("trip_engine"), "A stale marker cannot satisfy a dependency")
            manager.enable("trip_engine")
            manager.start("trip_engine")  # 恢复运行按钮后仍必须允许实际启动。
        finally:
            manager.close()

    def test_service_without_registration_ignores_live_run_marker(self):
        marker = self.root / "data" / "_registry" / "trip_engine.run"
        marker.write_text(json.dumps({"module_id": "trip_engine", "pid": os.getpid()}), encoding="utf-8")
        card = self.card()
        self.assertEqual(card["service"]["health"], "no_port")
        self.assertFalse(card["external"])
        self.assertEqual(card["status"], "stopped")

    def test_non_service_module_run_marker_is_honoured(self):
        """非服务型模块没有注册文件，靠运行标记判活 —— 否则 --all 会把 heartbeat 起两份。"""
        plain = self.root / "modules" / "heartbeat"
        plain.mkdir()
        (plain / "manifest.json").write_text(json.dumps(
            {"id": "heartbeat", "name": "心跳示例", "version": "1.0.0", "dependencies": []}),
            encoding="utf-8")
        (plain / "plugin.py").write_text("def run(ctx):\n    pass\n", encoding="utf-8")
        (self.root / "data" / "_registry" / "heartbeat.run").write_text(
            json.dumps({"module_id": "heartbeat", "pid": os.getpid(), "started_at": 1791819600}),
            encoding="utf-8")

        manager = Manager(self.root)
        try:
            card = next(item for item in manager.list() if item["id"] == "heartbeat")
            self.assertEqual(card["status"], "running")
            self.assertTrue(card["external"])
            with self.assertRaises(ValueError) as caught:
                manager.start("heartbeat")
            self.assertIn("已经在运行", str(caught.exception))
        finally:
            manager.close()

    def test_stale_run_marker_with_dead_pid_is_ignored(self):
        plain = self.root / "modules" / "heartbeat"
        plain.mkdir()
        (plain / "manifest.json").write_text(json.dumps(
            {"id": "heartbeat", "name": "心跳示例", "version": "1.0.0", "dependencies": []}),
            encoding="utf-8")
        (plain / "plugin.py").write_text("def run(ctx):\n    pass\n", encoding="utf-8")
        (self.root / "data" / "_registry" / "heartbeat.run").write_text(
            json.dumps({"module_id": "heartbeat", "pid": dead_pid(), "started_at": 1791819600}),
            encoding="utf-8")
        card = next(item for item in Manager(self.root).list() if item["id"] == "heartbeat")
        self.assertFalse(card["external"])
        self.assertEqual(card["status"], "stopped")


class StartAllIdempotencyTests(unittest.TestCase):
    """`start_software.py --all` 必须幂等：已经在跑的模块跳过，不再重复 spawn。"""

    class FakeManager:
        def __init__(self, cards):
            self.cards = cards
            self.spawned = []
            self.enabled = []

        def list(self):
            return list(self.cards.values())

        def enable(self, module_id):
            self.enabled.append(module_id)

        def start(self, module_id):
            self.spawned.append(module_id)

    def card(self, module_id, status="stopped", external=False):
        return {"id": module_id, "status": status, "external": external, "enabled": True, "error": ""}

    def test_already_running_modules_are_skipped_not_respawned(self):
        import start_software

        cards = {
            "trip_engine": self.card("trip_engine", status="running", external=True),
            "rules_engine": self.card("rules_engine", status="stopped"),
        }
        manager = self.FakeManager(cards)
        started = start_software.start_all(None, manager, ["trip_engine", "rules_engine"],
                                           {"rules_engine": False}, {})
        self.assertEqual(manager.spawned, ["rules_engine"])      # 外部实例没被重复启动
        self.assertEqual(manager.enabled, [])                    # 也没被重复 enable
        self.assertEqual(sorted(started), ["rules_engine", "trip_engine"])

    def test_modules_needing_enable_are_enabled_before_start(self):
        import start_software

        cards = {"rules_engine": self.card("rules_engine", status="stopped")}
        manager = self.FakeManager(cards)
        start_software.start_all(None, manager, ["rules_engine"], {"rules_engine": True}, {})
        self.assertEqual(manager.enabled, ["rules_engine"])
        self.assertEqual(manager.spawned, ["rules_engine"])


if __name__ == "__main__":
    unittest.main()
