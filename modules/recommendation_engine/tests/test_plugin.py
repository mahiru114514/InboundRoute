import importlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from contracts.runtime import registry
from modules.recommendation_engine.tests.test_service import Upstream


class PluginTests(unittest.TestCase):
    def load(self):
        try:
            return importlib.import_module('modules.recommendation_engine.plugin')
        except ModuleNotFoundError:
            self.fail('recommendation plugin implementation is missing')

    def test_manifest_dependency_and_package_loader(self):
        plugin = self.load()
        path = Path(plugin.__file__)
        manifest = json.loads((path.parent / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['dependencies'], ['trip_engine'])
        self.assertEqual(manifest['id'], 'recommendation_engine')
        spec = importlib.util.spec_from_file_location('recommendation_loader_test', path,
                                                      submodule_search_locations=[str(path.parent)])
        loaded = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = loaded
        try:
            spec.loader.exec_module(loaded)
            self.assertTrue(callable(loaded.run))
        finally:
            for name in list(sys.modules):
                if name == spec.name or name.startswith(spec.name + '.'):
                    del sys.modules[name]

    def test_registers_and_cleans_up_without_modifying_user_data(self):
        plugin = self.load()
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            context = SimpleNamespace(config={}, log=lambda message: None, wait=lambda seconds: True)
            record = SimpleNamespace(base_url='http://127.0.0.1:1', token='upstream')
            with patch.object(plugin, 'WORKSPACE', workspace), \
                 patch.object(plugin.registry, 'wait_for_registration', return_value=(record, {'status': 'ok'})), \
                 patch.object(plugin, 'TripEngineClient', return_value=Upstream()) as factory:
                plugin.run(context)
                factory.assert_called_once()
                self.assertIsNotNone(factory.call_args.kwargs.get('resolver'))
            self.assertIsNone(registry.try_read(workspace, 'recommendation_engine'))
            self.assertTrue((registry.registry_dir(workspace) / '_ports' / 'recommendation_engine.json').exists())


if __name__ == '__main__':
    unittest.main()
