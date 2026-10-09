import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from core.manager import Manager


def archive(module_id="demo", dependencies=None, extra=None, code=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("manifest.json", json.dumps({"id": module_id, "name": module_id,
            "version": "1.0.0", "dependencies": dependencies or []}))
        z.writestr("plugin.py", code or "def run(ctx):\n    ctx.log('started')\n    while not ctx.wait(0.05):\n        pass\n")
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return stream.getvalue()


def folder_files(extra=None):
    files = {"manifest.json": json.dumps({"id": "demo", "name": "本地模块", "version": "1.0.0"}),
             "plugin.py": "def run(ctx):\n    ctx.log('local')\n"}
    files.update(extra or {})
    return files


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = Manager(self.root)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def test_install_disabled_and_duplicate_preserves_original(self):
        self.manager.install(archive())
        self.assertFalse(self.manager.list()[0]["enabled"])
        with self.assertRaises(ValueError):
            self.manager.install(archive())
        self.assertTrue((self.root / "modules/demo/plugin.py").is_file())

    def test_reject_unsafe_archive_without_partial_install(self):
        for path in ("../escape.py", "C:/escape.py", "sub\\escape.py", "aux.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                # Windows 上 ZipInfo 构造时会规范化反斜杠；修改原始 ZIP 来测试外部恶意包。
                payload = archive(extra={path: "bad"})
                if "\\" in path:
                    payload = payload.replace(path.replace("\\", "/").encode(), path.encode())
                self.manager.install(payload)
        self.assertEqual(self.manager.list(), [])

    def test_dependencies_protect_disable_stop_uninstall(self):
        self.manager.install(archive("base"))
        self.manager.install(archive("child", ["base"]))
        with self.assertRaises(ValueError):
            self.manager.enable("child")
        self.manager.enable("base")
        self.manager.enable("child")
        with self.assertRaises(ValueError):
            self.manager.disable("base")
        with self.assertRaises(ValueError):
            self.manager.uninstall("base")
        self.manager.start("base")
        self.manager.start("child")
        with self.assertRaises(ValueError):
            self.manager.stop("base")
        self.manager.stop("child")
        self.manager.stop("base")

    def test_missing_and_cyclic_dependencies(self):
        self.manager.install(archive("a", ["b"]))
        with self.assertRaises(ValueError):
            self.manager.enable("a")
        self.manager.install(archive("b", ["a"]))
        with self.assertRaises(ValueError):
            self.manager.enable("a")

    def test_run_stop_config_and_persistence(self):
        self.manager.install(archive())
        self.manager.configure("demo", {"message": "你好"})
        self.manager.enable("demo")
        self.manager.start("demo")
        self.assertEqual(self.manager.list()[0]["status"], "running")
        with self.assertRaises(ValueError):
            self.manager.configure("demo", {})
        deadline = time.monotonic() + 5
        while "started" not in self.manager.logs("demo") and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertIn("started", self.manager.logs("demo"))
        self.manager.stop("demo")
        other = Manager(self.root)
        self.assertTrue(other.list()[0]["enabled"])
        self.assertEqual(other.config("demo"), {"message": "你好"})
        self.assertEqual(other.list()[0]["status"], "stopped")

    def test_install_from_folder(self):
        self.manager.install_folder("demo", folder_files({"helper.py": "value = 1\n"}))
        self.assertFalse(self.manager.list()[0]["enabled"])
        self.assertTrue((self.root / "modules/demo/helper.py").is_file())
        with self.assertRaises(ValueError):
            self.manager.install_folder("demo", folder_files())

    def test_folder_install_rejects_mismatch_and_unsafe_paths(self):
        with self.assertRaises(ValueError):
            self.manager.install_folder("other", folder_files())
        for name in ("../escape.py", "sub/../escape.py", "a\\b.py", "aux.txt", "trailing.py."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.manager.install_folder("demo", folder_files({name: "bad"}))
        with self.assertRaises(ValueError):
            self.manager.install_folder("demo", {"plugin.py": "def run(ctx): pass"})
        self.assertEqual(self.manager.list(), [])

    def test_broken_module_does_not_hide_others(self):
        self.manager.install(archive())
        broken = self.root / "modules/broken"
        broken.mkdir()
        (broken / "manifest.json").write_text("bad", encoding="utf-8")
        rows = self.manager.list()
        self.assertEqual(len(rows), 2)
        self.assertTrue(next(x for x in rows if x["id"] == "broken")["error"])

    def test_empty_module_folder_explains_what_is_missing(self):
        """空目录以前退化成英文 FileNotFoundError，界面上只能看到「格式异常」。"""
        self.manager.install(archive())
        (self.root / "modules/test_demo").mkdir()
        card = next(x for x in self.manager.list() if x["id"] == "test_demo")
        self.assertEqual(card["status"], "invalid")
        self.assertIn("是空的", card["error"])
        self.assertIn("manifest.json", card["error"])
        self.assertIn("examples/", card["error"])          # 必须给出下一步动作

    def test_incomplete_module_folder_names_the_missing_piece(self):
        """「有 manifest 但缺 plugin.py」和「有文件但没 manifest」都要说清缺的是什么。"""
        half = self.root / "modules/half"
        half.mkdir(parents=True)
        (half / "manifest.json").write_text(
            json.dumps({"id": "half", "name": "半成品", "version": "1.0.0"}), encoding="utf-8")
        card = next(x for x in self.manager.list() if x["id"] == "half")
        self.assertIn("plugin.py", card["error"])

        partial = self.root / "modules/partial"
        partial.mkdir(parents=True)
        (partial / "notes.txt").write_text("还没写完", encoding="utf-8")
        card = next(x for x in self.manager.list() if x["id"] == "partial")
        self.assertIn("不完整", card["error"])
        self.assertIn("manifest.json", card["error"])
        self.assertNotIn("是空的", card["error"])     # 目录里有东西，不能说成空目录

    def test_uninstall_preserves_config_and_data(self):
        self.manager.install(archive())
        self.manager.configure("demo", {"saved": True})
        data = self.root / "data/demo"
        data.mkdir(parents=True)
        (data / "result.txt").write_text("keep")
        self.manager.uninstall("demo")
        self.assertEqual(self.manager.list(), [])
        self.assertTrue((data / "result.txt").exists())
        self.manager.install(archive())
        self.assertEqual(self.manager.config("demo"), {"saved": True})


if __name__ == "__main__":
    unittest.main()
