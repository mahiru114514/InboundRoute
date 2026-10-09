"""推荐器、行程引擎与工作台的完整真实 HTTP 链路。"""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None
from contracts.runtime import registry
from modules.recommendation_engine.client import TripEngineClient
from modules.recommendation_engine.service import RecommendationService
from modules.recommendation_engine.http_api import build_server as recommendation_server
from modules.trip_engine.service import TripService
from modules.trip_engine.http_api import build_server as trip_server
from modules.web_workbench.engine import build_server as workbench_server
from modules.web_workbench.proxy import ServiceRegistry
from tests.test_trip_engine import new_trip_payload, BUND


class RecommendationIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.trips = TripService(self.root / 'data' / 'trip_engine')
        trip = trip_server(self.trips, 'trip-token')
        self.start(trip)
        registry.write(registry.build_registration('trip_engine', trip.server_port, 'trip-token'), self.root)
        client = TripEngineClient(f'http://127.0.0.1:{trip.server_port}', 'trip-token')
        recommendation = recommendation_server(RecommendationService(client), 'rec-token')
        self.start(recommendation)
        registry.write(registry.build_registration('recommendation_engine', recommendation.server_port, 'rec-token'), self.root)
        self.web = workbench_server(ServiceRegistry(self.root, ready_ttl=0, not_ready_ttl=0),
                                    'web-token', maps={'provider':'none','ready':False})
        self.start(self.web)

    def start(self, server):
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

    def post(self, path, payload, version=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.web.server_port, timeout=10)
        headers = {'Content-Type':'application/json', 'X-Workbench-Token':'web-token',
                   'Origin':f'http://127.0.0.1:{self.web.server_port}'}
        if version is not None:
            headers['If-Match'] = str(version)
        try:
            connection.request('POST', path, json.dumps(payload), headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def generate(self, source, days=(2,3,4)):
        status, response = self.post('/api/recommendations:generate', {**source,'day_indices':list(days)})
        self.assertEqual(status, 200, response)
        result = response['data']
        schema = json.loads((Path(__file__).resolve().parents[1] /
                             'contracts/schemas/recommendation.schema.json').read_text(encoding='utf-8'))
        if Draft202012Validator is not None:
            Draft202012Validator(schema).validate(result)
        return result

    def test_new_trip_is_created_once_only_after_complete_plan(self):
        setup = new_trip_payload(duration_days=5)
        setup['anchor_hotel'] = {'name_en':'我的酒店','name_zh':'我的酒店',
                                'coordinate':{'lat':31.23,'lng':121.48,'crs':'WGS84'}}
        proposal = self.generate({'setup':setup})
        self.assertIsNone(proposal['trip_id'])
        self.assertIsNone(proposal['trip_version'])
        self.assertEqual(self.trips.store.list_trips(), [])
        self.assertTrue(any(day['stops'] for day in proposal['plan']['days']))
        status, response = self.post('/api/trips:recommended', {'setup':setup,'plan':proposal['plan']})
        self.assertEqual(status, 201, response)
        trip = response['data']
        self.assertEqual(trip['anchor_hotel']['name_zh'], '我的酒店')
        self.assertEqual(trip['version'], 1)
        self.assertEqual(len(self.trips.store.list_trips()), 1)
        self.assertEqual(trip['days'][0]['ordered_stops'], [])
        self.assertEqual(trip['days'][-1]['ordered_stops'], [])
        for day in trip['days']:
            for stop in day['ordered_stops']:
                self.assertFalse(stop['locked'])

    def test_existing_days_are_skipped_and_applied_plan_uses_snapshot_version(self):
        trip = self.trips.create_trip(new_trip_payload(duration_days=5))
        trip = self.trips.add_stop(trip['trip_id'], 2, {'poi_id':BUND, 'locked':True})['trip']
        before = trip['days'][1]
        proposal = self.generate({'trip_id':trip['trip_id']})
        self.assertEqual(proposal['trip_version'], trip['version'])
        self.assertIn(2, [day['day_index'] for day in proposal['skipped_days']])
        self.assertNotIn(BUND, [stop['poi_id'] for day in proposal['plan']['days'] for stop in day['stops']])
        status, response = self.post('/api/trips/' + trip['trip_id'] + '/recommendations:apply',
                                    {'plan':proposal['plan']}, proposal['trip_version'])
        self.assertEqual(status, 200, response)
        self.assertEqual(response['data']['days'][1], before)
        self.assertEqual(response['data']['version'], trip['version'] + 1)

    def test_generation_failure_leaves_no_trip_and_old_plan_cannot_overwrite_edits(self):
        status, response = self.post('/api/recommendations:generate',
                                    {'setup':new_trip_payload(duration_days=5),'day_indices':[6]})
        self.assertEqual(status, 400, response)
        self.assertEqual(self.trips.store.list_trips(), [])
        trip = self.trips.create_trip(new_trip_payload(duration_days=5))
        proposal = self.generate({'trip_id':trip['trip_id']})
        edited = self.trips.add_stop(trip['trip_id'], 2, {'poi_id':BUND})['trip']
        status, response = self.post('/api/trips/' + trip['trip_id'] + '/recommendations:apply',
                                    {'plan':proposal['plan']}, proposal['trip_version'])
        self.assertEqual(status, 409, response)
        self.assertEqual(self.trips.get_trip(trip['trip_id']), edited)


if __name__ == '__main__':
    unittest.main()
