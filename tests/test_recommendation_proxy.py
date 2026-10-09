"""真实工作台 HTTP 验证推荐代理、新建原子写入、版本保护和鉴权。"""
import concurrent.futures
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from contracts.runtime import registry
from modules.trip_engine.service import TripService
from modules.trip_engine.http_api import build_server as trip_server
from modules.web_workbench.engine import build_server as workbench_server
from modules.web_workbench.proxy import ServiceRegistry
from tests.test_trip_engine import new_trip_payload, BUND, MUSEUM


class RecommendationProxyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = TripService(self.root / 'data' / 'trip_engine')
        self.upstream = trip_server(self.service, 'trip-token')
        self.start(self.upstream)
        registry.write(registry.build_registration('trip_engine', self.upstream.server_port, 'trip-token'), self.root)
        self.registry = ServiceRegistry(self.root, ready_ttl=0, not_ready_ttl=0)
        self.server = workbench_server(self.registry, 'web-token', maps={'provider':'none','ready':False})
        self.start(self.server)

    def start(self, server):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def call(self, path, payload=None, version=None, authorized=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Content-Type':'application/json','Origin':f'http://127.0.0.1:{self.server.server_port}'}
        if authorized:
            headers['X-Workbench-Token'] = 'web-token'
        if version is not None:
            headers['If-Match'] = str(version)
        try:
            conn.request('POST', path, json.dumps(payload or {}), headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def body(self, index=2, poi=BUND):
        return {'plan':{'days':[{'day_index':index,'stops':[{'poi_id':poi,'planned_dwell_minutes':90}]}]}}

    def test_preview_and_create_recommendation_through_workbench(self):
        setup = new_trip_payload(duration_days=5)
        status, preview = self.call('/api/trips:preview', setup)
        self.assertEqual(status, 200, preview)
        self.assertEqual(self.service.store.list_trips(), [])
        status, result = self.call('/api/trips:recommended', {'setup':setup, **self.body()})
        self.assertEqual(status, 201, result)
        self.assertEqual(result['data']['days'][1]['ordered_stops'][0]['poi_id'], BUND)

    def test_post_forwards_if_match_and_stale_version_returns_conflict(self):
        trip = self.service.create_trip(new_trip_payload(duration_days=5))
        path = '/api/trips/' + trip['trip_id'] + '/recommendations:apply'
        status, result = self.call(path, self.body(), version=1)
        self.assertEqual(status, 200, result)
        status, result = self.call(path, self.body(3,MUSEUM), version=1)
        self.assertEqual(status, 409, result)
        self.assertEqual(result['error']['code'], 'VERSION_CONFLICT')

    def test_same_version_concurrent_recommendations_have_one_winner(self):
        trip = self.service.create_trip(new_trip_payload(duration_days=5))
        path = '/api/trips/' + trip['trip_id'] + '/recommendations:apply'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            requests = [pool.submit(self.call, path, self.body(index,poi), 1)
                        for index,poi in [(2,BUND),(3,MUSEUM)]]
            statuses = [request.result()[0] for request in requests]
        self.assertEqual(sorted(statuses), [200,409])
        self.assertEqual(self.service.get_trip(trip['trip_id'])['version'], 2)

    def test_new_routes_cannot_bypass_browser_token(self):
        for path in ('/api/trips:preview','/api/trips:recommended','/api/recommendations:generate'):
            with self.subTest(path=path):
                self.assertEqual(self.call(path, authorized=False)[0], 403)
        self.assertEqual(self.service.store.list_trips(), [])

    def test_missing_recommender_has_explicit_degradation(self):
        status, result = self.call('/api/recommendations:generate', {'setup':new_trip_payload(),'day_indices':[1]})
        self.assertEqual(status, 503, result)
        self.assertIn('recommendation_engine', result['error']['message'])

    def test_generator_gets_payload_and_module_token(self):
        class Echo(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, data):
                raw = json.dumps({'ok':True,'data':data}).encode()
                self.send_response(200)
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                self.reply({'ready':True,'status':'ok'})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.reply({'path':self.path,'payload':payload,'token':self.headers.get('X-Module-Token')})

        echo = ThreadingHTTPServer(('127.0.0.1',0), Echo)
        self.start(echo)
        registry.write(registry.build_registration('recommendation_engine', echo.server_port, 'rec-token'), self.root)
        payload = {'trip_id':'trip_example','day_indices':[2,3]}
        status, result = self.call('/api/recommendations:generate', payload)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['data']['path'], '/recommendations:generate')
        self.assertEqual(result['data']['payload'], payload)
        self.assertEqual(result['data']['token'], 'rec-token')


if __name__ == '__main__':
    unittest.main()
