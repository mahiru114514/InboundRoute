import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from core.manager import Manager
from core.server import create_server
from test_manager import archive


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = Manager(Path(self.temp.name))
        self.server = create_server(self.manager, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.manager.close()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        self.client.request(method, path, body=data, headers=headers or {})
        response = self.client.getresponse()
        return response.status, response.read()

    def test_page_and_install_enable_config(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("模块工作台", page.decode())
        _, data = self.request("GET", "/api/state")
        token = json.loads(data)["token"]
        headers = {"X-Manager-Token": token}
        status, _ = self.request("POST", "/api/install", archive(), headers)
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/api/modules/demo/enable", b"{}", headers)
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/api/modules/demo/config", b'{"a":1}', headers)
        self.assertEqual(status, 200)
        _, data = self.request("GET", "/api/modules/demo")
        self.assertEqual(json.loads(data)["config"], {"a": 1})

    def test_write_requires_token_and_rejects_cross_origin(self):
        status, _ = self.request("POST", "/api/install", archive())
        self.assertEqual(status, 403)
        headers = {"X-Manager-Token": self.server.token, "Origin": "https://evil.example"}
        status, _ = self.request("POST", "/api/install", archive(), headers)
        self.assertEqual(status, 403)

    def test_folder_install_and_bad_format(self):
        headers = {"X-Manager-Token": self.server.token, "X-Install-Format": "folder"}
        payload = json.dumps({"folder": "demo", "files": {
            "manifest.json": base64.b64encode(b'{"id":"demo","name":"demo","version":"1.0.0"}').decode(),
            "plugin.py": base64.b64encode(b"def run(ctx):\n    pass\n").decode()}}).encode()
        status, data = self.request("POST", "/api/install", payload, headers)
        self.assertEqual(status, 200)
        self.assertIn("demo", json.loads(data)["message"])
        self.assertEqual(self.manager.list()[0]["id"], "demo")
        bad = {"X-Manager-Token": self.server.token, "X-Install-Format": "folder"}
        status, data = self.request("POST", "/api/install", json.dumps(
            {"folder": "demo", "files": {"plugin.py": base64.b64encode(b"def run(ctx): pass").decode()}}).encode(), bad)
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(data))

    def test_malformed_json_and_invalid_zip_are_reported(self):
        headers = {"X-Manager-Token": self.server.token}
        status, data = self.request("POST", "/api/install", b"bad zip", headers)
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(data))


if __name__ == "__main__":
    unittest.main()
