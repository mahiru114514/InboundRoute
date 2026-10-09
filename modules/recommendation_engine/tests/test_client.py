import importlib
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from modules.recommendation_engine.tests.common import poi, trip


class ClientTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('modules.recommendation_engine.client')
        except ModuleNotFoundError:
            self.fail('recommendation upstream client implementation is missing')
        self.calls = []
        self.payload = {'ok': True, 'data': trip()}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                owner.calls.append((self.path, self.headers.get('X-Module-Token')))
                raw = json.dumps(owner.payload).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                owner.calls.append((self.path, self.headers.get('X-Module-Token'), json.loads(raw)))
                body = json.dumps(owner.payload).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        if hasattr(self, 'server'):
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(2)

    def test_read_trip_pois_and_preview_paths(self):
        client = self.module.TripEngineClient(self.base_url, 'test')
        self.assertEqual(client.get_trip('trip_example')['version'], 3)
        self.payload = {'ok': True, 'data': {'pois': [poi(1)]}}
        self.assertEqual(client.list_pois()['pois'][0]['poi_id'], 'sh_poi_00001')
        self.payload = {'ok': True, 'data': trip()}
        client.preview_trip({'duration_days': 5})
        self.assertEqual(self.calls, [('/trips/trip_example', 'test'), ('/pois', 'test'),
                                     ('/trips:preview', 'test', {'duration_days': 5})])

    def test_refreshes_registry_before_each_request(self):
        records = iter([SimpleNamespace(base_url=self.base_url, token='new1'),
                        SimpleNamespace(base_url=self.base_url, token='new2')])
        client = self.module.TripEngineClient('http://127.0.0.1:1', 'stale', resolver=lambda: next(records))
        client.get_trip('a')
        client.get_trip('b')
        self.assertEqual([call[1] for call in self.calls], ['new1', 'new2'])

    def test_missing_registration_fails_without_stale_request(self):
        client = self.module.TripEngineClient(self.base_url, 'stale', resolver=lambda: None)
        with self.assertRaises(self.module.UpstreamError) as caught:
            client.get_trip('a')
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.calls, [])

    def test_non_envelope_response_is_bad_response(self):
        client = self.module.TripEngineClient(self.base_url, 'test')
        for response in [[], None, {'ok': True}, {'ok': True, 'data': []}]:
            self.payload = response
            with self.subTest(response=response), self.assertRaises(self.module.UpstreamError) as caught:
                client.get_trip('a')
            self.assertEqual(caught.exception.code, 'UPSTREAM_BAD_RESPONSE')

    def test_upstream_errors_propagated(self):
        self.payload = {'ok': False, 'error': {'code': 'TRIP_NOT_FOUND', 'message': 'not found'}}
        with self.assertRaises(self.module.UpstreamError) as caught:
            self.module.TripEngineClient(self.base_url, 'test').get_trip('a')
        self.assertEqual(caught.exception.code, 'TRIP_NOT_FOUND')
        self.assertEqual(caught.exception.status, 502)


if __name__ == '__main__':
    unittest.main()
