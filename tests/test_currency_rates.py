"""参考汇率解析、缓存及隔离 HTTP 入口。"""
import http.client
import io
import json
import threading
import unittest
from unittest.mock import Mock

from modules.web_workbench.currency_rates import CurrencyRates, CurrencyRateError
from modules.web_workbench.engine import build_server


def quote(**changes):
    return {'date':'2026-10-06','base':'USD','quote':'CNY','rate':6.7, **changes}


class CurrencyRatesTests(unittest.TestCase):
    def service(self, payload=None):
        self.now = 1.0
        self.opener = Mock(side_effect=lambda *args, **kwargs:io.BytesIO(json.dumps(payload or quote()).encode()))
        return CurrencyRates(opener=self.opener, clock=lambda:self.now)

    def test_reference_rate_direction_source_date_and_cache(self):
        service = self.service()
        first = service.get('USD')
        self.assertEqual(first['cny_per_unit'], 6.7)
        self.assertEqual(first['date'], '2026-10-06')
        self.assertEqual(first['source'], 'Frankfurter')
        self.assertTrue(first['source_url'].startswith('https://'))
        self.assertFalse(first['cached'])
        second = service.get('USD')
        self.assertTrue(second['cached'])
        self.assertEqual(self.opener.call_count, 1)
        request = self.opener.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.frankfurter.dev/v2/rate/usd/cny')
        self.assertEqual(request.get_header('User-agent'), 'InboundRoute/1.0')

    def test_explicit_refresh_fetches_and_failure_uses_only_marked_previous_rate(self):
        service = self.service()
        service.get('USD')
        service.get('USD', refresh=True)
        self.assertEqual(self.opener.call_count, 2)
        self.opener.side_effect = TimeoutError('unavailable')
        self.now += 6 * 3600 + 1
        stale = service.get('USD')
        self.assertTrue(stale['stale'])
        self.assertEqual(stale['cny_per_unit'], 6.7)
        self.assertIn('warning', stale)

    def test_invalid_currency_never_performs_network_request(self):
        service = self.service()
        for code in ('http://localhost', 'ZZZ', 'USD/../../', '', ['USD']):
            with self.subTest(code=code), self.assertRaises(CurrencyRateError):
                service.get(code)
        self.opener.assert_not_called()

    def test_bad_quotes_do_not_become_cached_rates(self):
        for changes in ({'rate':-1}, {'rate':True}, {'rate':float('nan')}, {'rate':float('inf')},
                        {'base':'EUR'}, {'quote':'USD'}, {'date':'not-a-date'}, {'rate':0}):
            with self.subTest(changes=changes), self.assertRaises(CurrencyRateError):
                self.service(quote(**changes)).get('USD')

    def test_timeout_and_oversized_response_do_not_invent_fallback(self):
        for response in (TimeoutError('unavailable'), io.BytesIO(b' ' * 65537)):
            service = self.service()
            self.opener.side_effect = response if isinstance(response, Exception) else lambda *a, **k:response
            with self.assertRaises(CurrencyRateError):
                service.get('USD')

    def test_http_requires_session_token_and_returns_validated_query(self):
        rates = self.service()
        server = build_server(Mock(), 'fx-test-token', 0, maps={'ready':False}, currency_rates=rates)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            connection.request('GET', '/api/currency-rates?currency=USD')
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 403)
            self.opener.assert_not_called()
            connection.request('GET', '/api/currency-rates?currency=USD', headers={'X-Workbench-Token':'fx-test-token'})
            response = connection.getresponse()
            body = json.loads(response.read())
            self.assertEqual(response.status, 200, body)
            self.assertEqual(body['data']['currency'], 'USD')
            connection.request('GET', '/api/currency-rates?currency=ZZZ', headers={'X-Workbench-Token':'fx-test-token'})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 400)
        finally:
            connection.close()
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
