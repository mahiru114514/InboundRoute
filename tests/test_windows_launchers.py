"""Exercise Windows batch parsing and Chinese output under a Chinese path."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows batch launchers")
class WindowsLauncherTests(unittest.TestCase):
    def test_launchers_handle_chinese_paths_and_output(self):
        for batch, entry in (("start_software.bat", "start_software.py"),
                             ("start.bat", "manager.py")):
            with self.subTest(batch=batch), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp) / "中文 启动目录"
                folder.mkdir()
                shutil.copyfile(ROOT / batch, folder / batch)
                (folder / entry).write_text(
                    "from pathlib import Path\nimport sys\n"
                    "print('中文启动正常')\n"
                    "print(Path.cwd().name)\n"
                    "print(repr(sys.argv[1:]))\n",
                    encoding="utf-8",
                )
                env = dict(os.environ, PYTHONIOENCODING="gbk", PYTHONUTF8="0")
                env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
                args = ' --list "参数 含空格"' if batch == "start_software.bat" else ""
                comspec = os.environ.get("COMSPEC", "cmd.exe")
                result = subprocess.run(
                    f'"{comspec}" /d /c {batch}{args}',
                    cwd=folder, env=env, input=b"", capture_output=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                self.assertIn("中文启动正常".encode("utf-8"), result.stdout)
                self.assertIn(folder.name.encode("utf-8"), result.stdout)
                if args:
                    self.assertIn("['--list', '参数 含空格']".encode("utf-8"), result.stdout)


if __name__ == "__main__":
    unittest.main()
