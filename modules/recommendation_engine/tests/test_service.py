import http.client
import importlib
import json
import threading
import unittest

from modules.recommendation_engine.tests.common import poi, trip


class Upstream:
    def __init__(self):
        self.calls = []
        self.ready = True

    def get_trip(self, trip_id):
        self.calls.append(('get', trip_id))
        return trip()

    def preview_trip(self, setup):
        self.calls.append(('preview', setup))
        return trip()

    def list_pois(self):
        self.calls.append(('pois',))
        return {'pois': [poi(i) for i in range(8)]}

    def health(self):
        return {'ok': True, 'data': {'ready': True, 'status': 'ok'}} if self.ready else None


class ServiceTests(unittest.TestCase):
    def setUp(self):
        try:
            service = importlib.import_module('modules.recommendation_engine.service')
            http_api = importlib.import_module('modules.recommendation_engine.http_api')
        except ModuleNotFoundError:
            self.fail('recommendation HTTP service implementation is missing')
        self.upstream = Upstream()
        self.service = service.RecommendationService(self.upstream)
        self.server = http_api.build_server(self.service, 'secret')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        if hasattr(self, 'server'):
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)

    def request(self, path='/recommendations:generate', payload=None, method='POST', token='secret', host=None, raw=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['X-Module-Token'] = token
        if host:
            headers['Host'] = host
        body = raw if raw is not None else json.dumps(payload)
        connection.request(method, path, body=body if method == 'POST' else None, headers=headers)
        response = connection.getresponse()
        status, result = response.status, json.loads(response.read())
        connection.close()
        return status, result

    def test_existing_trip_response_envelope_and_read_only_calls(self):
        status, result = self.request(payload={'trip_id': 'trip_example', 'day_indices': [2, 3]})
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['trip_id'], 'trip_example')
        self.assertEqual(result['data']['trip_version'], 3)
        self.assertEqual(self.upstream.calls, [('get', 'trip_example'), ('pois',)])

    def test_preview_response_never_exposes_temporary_id(self):
        status, result = self.request(payload={'setup': {'duration_days': 5}, 'day_indices': [2]})
        self.assertEqual(status, 200)
        self.assertIsNone(result['data']['trip_id'])
        self.assertIsNone(result['data']['trip_version'])
        self.assertEqual(self.upstream.calls[0][0], 'preview')

    def test_strict_body_validation(self):
        cases = [None, [], {}, {'trip_id': 'a', 'setup': {}, 'day_indices': [2]},
                 {'trip_id': 'a', 'day_indices': [2], 'other': 1}, {'trip_id': '', 'day_indices': [2]},
                 {'trip_id': '../a', 'day_indices': [2]}, {'setup': [], 'day_indices': [2]},
                 {'trip_id': 'a', 'day_indices': []}, {'trip_id': 'a', 'day_indices': [True]},
                 {'trip_id': 'a', 'day_indices': [2, 2]}, {'trip_id': 'a', 'day_indices': [99]}]
        for payload in cases:
            with self.subTest(payload=payload):
                status, result = self.request(payload=payload)
                self.assertEqual(status, 400)
                self.assertFalse(result['ok'])
                self.assertEqual(result['error']['code'], 'BAD_REQUEST')

    def test_invalid_json_standard_error(self):
        status, result = self.request(raw='{broken')
        self.assertEqual(status, 400)
        self.assertEqual(result['error']['code'], 'BAD_REQUEST')

    def test_token_and_host_required(self):
        for token, host in [(None, None), ('wrong', None), ('secret', 'evil.example')]:
            with self.subTest(token=token, host=host):
                status, result = self.request(payload={'trip_id': 'a', 'day_indices': [2]}, token=token, host=host)
                self.assertEqual(status, 403)
                self.assertFalse(result['ok'])

    def test_health_without_token_and_degraded_upstream(self):
        status, result = self.request('/health', method='GET', token=None)
        self.assertEqual(status, 200)
        self.assertTrue(result['data']['ready'])
        self.upstream.ready = False
        status, result = self.request('/health', method='GET', token=None)
        self.assertEqual(result['data']['status'], 'degraded')
        self.assertFalse(result['data']['ready'])

    def test_wrong_method_and_unknown_route(self):
        self.assertEqual(self.request(method='GET')[0], 405)
        self.assertEqual(self.request('/missing')[0], 404)

    def test_upstream_failure_uses_standard_error_envelope(self):
        from modules.recommendation_engine.client import UpstreamError
        def unavailable(_):
            raise UpstreamError(503, 'UPSTREAM_TIMEOUT', 'trip_engine unavailable')
        self.upstream.get_trip = unavailable
        status, result = self.request(payload={'trip_id': 'a', 'day_indices': [2]})
        self.assertEqual(status, 503)
        self.assertEqual(result['error']['code'], 'UPSTREAM_TIMEOUT')
        self.assertTrue(result['error']['retryable'])

    def test_duplicate_json_keys_and_nonfinite_values_rejected(self):
        for raw in ['{"trip_id":"a","trip_id":"b","day_indices":[2]}',
                    '{"setup":{"budget":NaN},"day_indices":[2]}']:
            with self.subTest(raw=raw):
                self.assertEqual(self.request(raw=raw)[0], 400)

    def test_non_ascii_invalid_token_returns_forbidden_envelope(self):
        status, result = self.request(payload={'trip_id': 'a', 'day_indices': [2]}, token='\u00e9')
        self.assertEqual(status, 403)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'FORBIDDEN')


if __name__ == '__main__':
    unittest.main()
