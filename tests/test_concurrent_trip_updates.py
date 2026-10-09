"""并发 HTTP 修改不能绕过版本检查或覆盖另一操作。"""
import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import test_trip_engine as trips


class ConcurrentTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = trips.TripService(Path(self.temp.name))
        self.server = trips.build_server(self.service, trips.TOKEN)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.trip = self.service.create_trip(trips.new_trip_payload())

    def request(self, method, path, payload, version=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'X-Module-Token': trips.TOKEN, 'Content-Type': 'application/json'}
        if version is not None:
            headers['If-Match'] = str(version)
        try:
            conn.request(method, path, json.dumps(payload), headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def concurrent_requests(self, requests):
        original = self.service.store.get
        barrier = threading.Barrier(2)
        def read_together(trip_id):
            result = original(trip_id)
            # 未加锁时让两个请求都先读到旧版本；加锁后第一个超时继续，
            # 第二个只能等第一个提交后读取。屏障破裂属于正常的串行路径。
            try:
                barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
            return result
        self.service.store.get = read_together
        try:
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(self.request, *args) for args in requests]
                return [future.result() for future in futures]
        finally:
            self.service.store.get = original

    def test_same_version_allows_only_one_patch(self):
        path = '/trips/' + self.trip['trip_id']
        results = self.concurrent_requests([
            ('PATCH', path, {'user_profile': {'pacing': 'packed'}}, 1),
            ('PATCH', path, {'daily_start_local': '11:00'}, 1),
        ])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        conflict = next(body for status, body in results if status == 409)
        self.assertEqual(conflict['error']['code'], 'VERSION_CONFLICT')
        self.assertEqual(self.service.get_trip(self.trip['trip_id'])['version'], 2)

    def test_concurrent_adds_preserve_both_stops(self):
        path = '/trips/' + self.trip['trip_id'] + '/days/2/stops'
        results = self.concurrent_requests([
            ('POST', path, {'poi_id': trips.BUND}),
            ('POST', path, {'poi_id': trips.MUSEUM}),
        ])
        self.assertEqual([status for status, _ in results], [201, 201])
        trip = self.service.get_trip(self.trip['trip_id'])
        self.assertEqual(trip['version'], 3)
        self.assertEqual({stop['poi_id'] for stop in trip['days'][1]['ordered_stops']},
                         {trips.BUND, trips.MUSEUM})


if __name__ == '__main__':
    unittest.main()
