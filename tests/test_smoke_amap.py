import contextlib
import io
import json
import socket
import ssl
import unittest
import urllib.error
from unittest.mock import patch

from tools import smoke_amap


class SmokeAmapDiagnosticsTests(unittest.TestCase):
    def run_smoke(self, modes='walk', diagnose=False, **request_options):
        output = io.StringIO()
        argv = ['smoke_amap.py', '--modes', modes, '--require-key']
        if diagnose:
            argv.append('--diagnose')
        with patch.dict('os.environ', {'AMAP_WEB_KEY': 'test-secret'}), \
                patch('sys.argv', argv), \
                patch.object(smoke_amap.AmapProvider, '_request_json', **request_options), \
                contextlib.redirect_stdout(output):
            exit_code = smoke_amap.main()
        self.assertNotIn('test-secret', output.getvalue())
        self.assertNotIn('https://', output.getvalue())
        return exit_code, json.loads(output.getvalue())['routes'][0]

    def test_business_code_survives_without_raw_provider_info(self):
        code, row = self.run_smoke(return_value={
            'status': '0', 'infocode': '10009', 'info': 'https://x?key=test-secret'})
        self.assertEqual(code, 1)
        self.assertEqual(row['reason'], 'partial_data')
        self.assertEqual(row['diagnostic'], {'category': 'service_error', 'provider_code': '10009'})
        self.assertIn('Web服务', row['hint'])

    def test_http_failure_keeps_only_status(self):
        code, row = self.run_smoke(side_effect=urllib.error.HTTPError(
            'https://x?key=test-secret', 403, 'test-secret', {}, None))
        self.assertEqual(code, 1)
        self.assertEqual(row['diagnostic'], {'category': 'http_error', 'http_status': 403})

    def test_certificate_failure_is_distinct_from_provider_rejection(self):
        _, row = self.run_smoke(side_effect=urllib.error.URLError(
            ssl.SSLCertVerificationError('test-secret')))
        self.assertEqual(row['diagnostic'], {'category': 'certificate_error'})

    def test_untrusted_infocode_is_not_echoed(self):
        _, row = self.run_smoke(return_value={
            'status': '0', 'infocode': 'https://x?key=test-secret', 'info': 'test-secret'})
        self.assertEqual(row['diagnostic'], {'category': 'service_error'})

    def test_invalid_json_is_distinct_from_incomplete_route(self):
        _, row = self.run_smoke(side_effect=ValueError('test-secret'))
        self.assertEqual(row['diagnostic'], {'category': 'invalid_json'})

    def test_network_failures_keep_safe_categories(self):
        for error, category, reason in [
            (TimeoutError('test-secret'), 'timeout', 'timeout'),
            (urllib.error.URLError(socket.gaierror('test-secret')), 'dns_error', 'partial_data'),
            (ConnectionResetError('test-secret'), 'network_error', 'partial_data'),
        ]:
            with self.subTest(category=category):
                _, row = self.run_smoke(side_effect=error)
                self.assertEqual(row['diagnostic'], {'category': category})
                self.assertEqual(row['reason'], reason)

    def test_incomplete_route_is_not_reported_as_key_error(self):
        _, row = self.run_smoke(return_value={
            'status': '1', 'route': {'paths': [{'duration': '90'}]}})
        self.assertEqual(row['diagnostic'], {'category': 'missing_route_fields'})

    def test_success_still_reports_real_metrics(self):
        code, row = self.run_smoke(return_value={
            'status': '1', 'route': {'paths': [{'distance': '120', 'duration': '90'}]}})
        self.assertEqual(code, 0)
        self.assertEqual(row['status'], 'passed')
        self.assertEqual(row['data_source'], 'amap')
        self.assertEqual(row['duration_seconds'], 90)

    def test_missing_transit_segment_duration_has_specific_diagnostic(self):
        for raw, category in [
            ({'walking': {'distance': '120', 'steps': []}}, 'walking_duration_missing'),
            ({'bus': {'buslines': [{'name': 'test-secret', 'distance': '120'}]}}, 'ride_duration_missing'),
        ]:
            with self.subTest(category=category):
                _, row = self.run_smoke(modes='transit', return_value={
                    'status': '1', 'route': {'transits': [{'duration': '90', 'segments': [raw]}]}})
                self.assertEqual(row['diagnostic'], {'category': category})

    def test_unsupported_transit_and_empty_segments_are_distinct(self):
        for segments, category in [
            ([{'taxi': {'name': 'test-secret'}}], 'unsupported_transit_segment'),
            ([], 'transit_segments_missing'),
        ]:
            with self.subTest(category=category):
                _, row = self.run_smoke(modes='transit', return_value={
                    'status': '1', 'route': {'transits': [{'duration': '90', 'segments': segments}]}})
                self.assertEqual(row['diagnostic'], {'category': category})

    def test_diagnose_summarizes_types_without_echoing_payload(self):
        _, row = self.run_smoke(modes='transit', diagnose=True, return_value={
            'status': '1', 'info': 'test-secret', 'route': {'transits': [{
                'duration': '90', 'segments': [{
                    'walking': {'distance': [], 'duration': [], 'steps': [
                        {'duration': '80', 'instruction': 'https://x?key=test-secret'}]},
                    'bus': {'buslines': []},
                    'taxi': {'name': 'test-secret'}, 'railway': {},
                }],
            }]}})
        summary = row['response_summary']
        self.assertEqual(summary['plan_count'], 1)
        segment = summary['plans'][0]['segments'][0]
        self.assertEqual(segment['walking']['duration'], 'empty')
        self.assertEqual(segment['walking']['step_count'], 1)
        self.assertEqual(segment['walking']['timed_step_count'], 1)
        self.assertTrue(segment['taxi_has_data'])
        self.assertFalse(segment['railway_has_data'])

    def test_real_transit_shape_with_empty_placeholders_passes_smoke(self):
        # Two legs: walk + bus, then walk. Walking steps need no duration
        # because the provider supplies a valid aggregate walking duration.
        code, row = self.run_smoke(modes='transit', diagnose=True, return_value={
            'status': '1', 'route': {'transits': [{
                'duration': '720', 'distance': '2400', 'walking_distance': '400',
                'segments': [{
                    'walking': {'distance': '200', 'duration': '160', 'steps': [
                        {'instruction': '沿道路步行'}]},
                    'bus': {'buslines': [{'name': '公交线路', 'duration': '400', 'distance': '2000'}]},
                    'railway': {'id': [], 'name': [], 'departure_stop': {}},
                    'taxi': {'origin': [], 'destination': [], 'distance': [], 'duration': []},
                }, {
                    'walking': {'distance': '200', 'duration': '160', 'steps': [
                        {'instruction': '步行至终点'}]},
                    'bus': {'buslines': []},
                    'railway': {'id': [], 'name': [], 'departure_stop': {}},
                    'taxi': {'origin': [], 'destination': [], 'distance': [], 'duration': []},
                }],
            }]}})
        self.assertEqual(code, 0)
        self.assertEqual(row['status'], 'passed')
        self.assertEqual(row['data_source'], 'amap')
        self.assertEqual(row['duration_seconds'], 720)
        self.assertEqual(row['distance_meters'], 2400)
        self.assertEqual(row['segment_count'], 3)
        self.assertFalse(row['response_summary']['plans'][0]['segments'][0]['taxi_has_data'])


if __name__ == '__main__':
    unittest.main()
