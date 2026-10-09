"""验证包内依赖、业务/HTTP 边界与宿主插件加载，防止同名模块互相抢占。"""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ModuleLoadingTests(unittest.TestCase):
    def run_python(self, source):
        result = subprocess.run([sys.executable, '-c', source], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_business_service_does_not_load_http_server(self):
        self.run_python('''
import sys
from modules.trip_engine.service import TripService
from modules.trip_engine.errors import EngineError
from modules.trip_engine.store import EngineError as StoreError
assert 'http.server' not in sys.modules
assert EngineError is StoreError
''')

    def test_two_engines_can_be_imported_without_global_name_collisions(self):
        self.run_python('''
import sys
before = list(sys.path)
from modules.trip_engine.engine import TripService, build_server as trip_server
from modules.web_workbench.engine import build_server as workbench_server
from modules.trip_engine.service import TripService as DirectService
assert TripService is DirectService
assert trip_server is not workbench_server
assert before == sys.path
assert not {'engine', 'store', 'proxy'} & sys.modules.keys()
''')

    def test_plugins_load_with_host_package_protocol(self):
        for module_id in ('trip_engine', 'web_workbench'):
            with self.subTest(module=module_id):
                self.run_python(f'''
import importlib.util
import sys
from pathlib import Path
folder = Path('modules') / {module_id!r}
spec = importlib.util.spec_from_file_location('user_plugin', folder / 'plugin.py',
                                            submodule_search_locations=[str(folder)])
plugin = importlib.util.module_from_spec(spec)
sys.modules['user_plugin'] = plugin
spec.loader.exec_module(plugin)
assert callable(plugin.run)
assert not {{'engine', 'store', 'proxy'}} & sys.modules.keys()
''')


if __name__ == '__main__':
    unittest.main()
