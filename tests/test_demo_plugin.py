import json
import logging
import tempfile
import threading
import unittest
from pathlib import Path

from core.runtime import Context
from examples.test_demo.plugin import run


class DemoTests(unittest.TestCase):
    def test_completes_and_writes_configured_message(self):
        with tempfile.TemporaryDirectory() as folder:
            context = Context({"count": 2, "interval": 0.01, "message": "测试成功"},
                              Path(folder), threading.Event(), logging.getLogger("test"))
            run(context)
            result = json.loads((Path(folder) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["completed"], 2)
            self.assertEqual(result["message"], "测试成功")

    def test_stop_request_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            event = threading.Event()
            event.set()
            run(Context({}, Path(folder), event, logging.getLogger("test")))
            result = json.loads((Path(folder) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["completed"], 0)

    def test_invalid_count_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                run(Context({"count": -1}, Path(folder), threading.Event(), logging.getLogger("test")))
