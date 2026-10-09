import unittest
from copy import deepcopy
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import json
import urllib.error
import common
from providers import AmapProvider, ProviderError
from crs import wgs84_to_gcj02

POINT = {'lat': 31.23, 'lng': 121.47, 'crs': 'WGS84'}
WALK = {'status': '1', 'route': {'paths': [{'distance': '120', 'duration': '90'}]}}
TRANSIT = {'status': '1', 'route': {'distance': '9999', 'transits': [{
    'duration': '600', 'cost': '4', 'walking_distance': '100', 'segments': [
        {'walking': {'distance': '100', 'duration': '80', 'steps': [{'instruction': '沿道路步行'}]},
         'bus': {'buslines': [{'id': 'line2', 'name': '地铁2号线', 'distance': '2000', 'duration': '400',
            'via_num': '2', 'departure_stop': {'id': 's1', 'name': '起点站'},
            'arrival_stop': {'id': 's2', 'name': '终点站'}}]}, 'entrance': {'name': '1号口'}}]}]}}
# 真实高德返回形态（取自实际离线包）：线路 id 是内部主键、线路名只在括号里给起讫点、
# 步行指引是中文长句、出入口只有名字没有编号。
REAL = {'status': '1', 'route': {'distance': '38000', 'transits': [{
    'duration': '7320', 'cost': '9', 'walking_distance': '2826', 'segments': [
        {'walking': {'distance': '1312', 'duration': '1050', 'steps': [
            {'instruction': '沿浦东机场路步行382米向左前方直行'},
            {'instruction': '步行24米右转'},
            {'instruction': '步行44米到达浦东1号2号航站楼'}]},
         'bus': {'buslines': [{'id': '900000160000',
            'name': '市域机场线(浦东1号2号航站楼--虹桥2号航站楼)',
            'distance': '30000', 'duration': '1500', 'via_num': '0',
            'departure_stop': {'id': 'B0FFF', 'name': '浦东1号2号航站楼'},
            'arrival_stop': {'id': 'B0FFG', 'name': '虹桥2号航站楼'}}]},
            'entrance': {'name': '1号口'}, 'exit': {'name': '2号口'}}]}]}}

class AmapTests(unittest.TestCase):
    def test_amap_chinese_station_names_gain_sourced_english(self):
        route, _ = self.compute(deepcopy(REAL), 'transit')
        ride = next(s for s in route['segments'] if s['kind'] == 'ride')
        self.assertEqual(ride['board']['station_name_en'], 'Pudong Airport Terminal 1 & 2')
        self.assertEqual(ride['alight']['station_name_en'], 'Hongqiao Airport Terminal 2')

    def test_walk_geometry_and_instructions_are_kept(self):
        payload=deepcopy(WALK)
        payload['route']['paths'][0]['steps']=[{'instruction':'向东步行', 'polyline':'121.47,31.23;121.471,31.231'}]
        result,_=self.compute(payload)
        self.assertIsNotNone(result.get('polyline'))
        self.assertNotEqual(result['polyline'].split(';')[0], '121.470000,31.230000')
        self.assertEqual(result['segments'][0]['walk_note_zh'],'向东步行')

    def test_incomplete_transit_geometry_is_not_drawn_as_complete(self):
        payload=deepcopy(TRANSIT)
        payload['route']['transits'][0]['segments'][0]['walking']['steps'][0]['polyline']='121.47,31.23;121.471,31.231'
        result,_=self.compute(payload,'transit')
        self.assertIsNone(result.get('polyline'))

    def compute(self, payload, mode='walk'):
        p = AmapProvider({'api_key': 'test-secret', 'city': '上海'})
        with patch.object(p, '_request_json', return_value=payload) as request:
            result = p.compute(POINT, POINT, mode, 'default', {})
        return result, request.call_args.args[0]

    def test_walk_real_nested_response_and_gcj_request(self):
        result, url = self.compute(WALK)
        self.assertEqual(result['distance_meters'], 120)
        self.assertEqual(result['duration_seconds'], 90)
        self.assertTrue(urlsplit(url).path.endswith('/v3/direction/walking'))
        lat, lng = wgs84_to_gcj02(31.23, 121.47)
        self.assertEqual(parse_qs(urlsplit(url).query)['origin'], [f'{lng:.6f},{lat:.6f}'])

    def test_taxi_uses_driving_and_provider_fare(self):
        r, url = self.compute({'status': '1', 'route': {'taxi_cost': '23.5', 'paths': [{'distance': '2100', 'duration': '300'}]}}, 'taxi')
        self.assertTrue(urlsplit(url).path.endswith('/v3/direction/driving'))
        self.assertEqual(r['cost']['min'], 23.5)
        self.assertIsNone(r['walking_distance_meters'])

    def test_transit_segments_and_no_invented_exit(self):
        r, url = self.compute(TRANSIT, 'transit')
        self.assertEqual(r['distance_meters'], 2100)
        self.assertEqual(r['segments'][1]['board']['station_name_zh'], '起点站')
        self.assertEqual(r['segments'][1]['board']['access_name_zh'], '1号口')
        self.assertIsNone(r['segments'][1]['alight']['access_name_zh'])
        self.assertIsNone(r['segments'][1]['direction'])
        self.assertEqual(parse_qs(urlsplit(url).query)['city'], ['上海'])

    def test_transit_ignores_empty_railway_and_taxi_placeholders(self):
        # A nonempty JSON object can contain only empty provider placeholders.
        # This reproduces the user's valid walking/bus plan rejected as unsupported.
        for empty in [
            {'id': [], 'duration': [], 'distance': []},
            {'departure_stop': {'id': [], 'name': ''}, 'arrival_stop': {}},
            {'origin': None, 'destination': '', 'steps': [None, {}]},
        ]:
            with self.subTest(placeholder=empty):
                payload = deepcopy(TRANSIT)
                leg = payload['route']['transits'][0]['segments'][0]
                leg['railway'] = deepcopy(empty)
                leg['taxi'] = deepcopy(empty)
                r, _ = self.compute(payload, 'transit')
                self.assertEqual(r['data_source'], 'amap')
                self.assertEqual(r['duration_seconds'], 600)
                self.assertEqual([s['kind'] for s in r['segments']], ['walk', 'ride'])

    def test_transit_still_rejects_actual_railway_or_taxi(self):
        for field, content in [('railway', {'name': '真实列车'}),
                               ('taxi', {'distance': '300', 'duration': '50'}),
                               ('taxi', {'duration': 0})]:
            with self.subTest(field=field):
                payload = deepcopy(TRANSIT)
                payload['route']['transits'][0]['segments'][0][field] = content
                with self.assertRaises(ProviderError) as raised:
                    self.compute(payload, 'transit')
                self.assertEqual(raised.exception.diagnostic['category'], 'unsupported_transit_segment')

    def test_missing_distance_not_fabricated(self):
        with self.assertRaises(ProviderError):
            self.compute({'status': '1', 'route': {'paths': [{'duration': '90'}]}})

    def test_error_redacts_key_and_rate_limit(self):
        for error, reason in [(TimeoutError('test-secret'), 'timeout'), (urllib.error.HTTPError('https://x?key=test-secret', 429, 'test-secret', {}, None), 'rate_limited')]:
            p = AmapProvider({'api_key': 'test-secret'})
            with patch.object(p, '_request_json', side_effect=error), self.assertRaises(ProviderError) as raised:
                p.compute(POINT, POINT, 'walk', 'default', {})
            self.assertEqual(raised.exception.reason, reason)
            self.assertNotIn('test-secret', str(raised.exception))

    def test_business_errors_and_empty_results(self):
        for payload, reason in [({'status': '0', 'infocode': '10003', 'info': 'test-secret'}, 'rate_limited'), ({'status': '1', 'route': {'paths': []}}, 'no_route')]:
            with self.assertRaises(ProviderError) as raised:
                self.compute(payload)
            self.assertEqual(raised.exception.reason, reason)
            self.assertNotIn('test-secret', str(raised.exception))

    def test_environment_key(self):
        with patch.dict('os.environ', {'AMAP_WEB_KEY': 'fixture-key'}):
            self.assertEqual(AmapProvider({}).api_key, 'fixture-key')

    def test_real_transit_line_identity_direction_access_and_walk_notes(self):
        route, _ = self.compute(deepcopy(REAL), 'transit')
        ride, walk = route['segments'][1], route['segments'][0]
        dumped = json.dumps(ride, ensure_ascii=False)
        # 三方主键绝不能当线路号下发
        self.assertNotIn('900000160000', dumped)
        self.assertNotIn('code', ride['line'])
        self.assertEqual(ride['line']['name_zh'], '市域机场线')
        self.assertEqual(ride['line']['name_en'], 'Airport Link Line')
        self.assertEqual(ride['direction'], {'name_zh': '往虹桥2号航站楼方向',
                                             'name_en': 'Towards Hongqiao Airport Terminal 2'})
        self.assertEqual(ride['board']['station_name_zh'], '浦东1号2号航站楼')
        self.assertEqual(ride['board']['access_no'], '1')
        self.assertEqual(ride['board']['access_name_en'], 'Entrance 1')
        self.assertEqual(ride['alight']['access_no'], '2')
        self.assertEqual(ride['alight']['access_name_en'], 'Exit 2')
        self.assertEqual(walk['walk_note_zh'],
                         '沿浦东机场路步行382米向左前方直行；步行24米右转；步行44米到达浦东1号2号航站楼')
        self.assertEqual(walk['walk_note_en'],
                         'Walk 382 m along Pudong Jichang Road, bear left and continue; '
                         'Walk 24 m, turn right; '
                         'Walk 44 m to reach Pudong Airport Terminal 1 & 2')

    def test_walk_mode_instructions_are_translated_too(self):
        payload = deepcopy(WALK)
        payload['route']['paths'][0]['steps'] = [{'instruction': '步行120米到达目的地'}]
        result, _ = self.compute(payload)
        self.assertEqual(result['segments'][0]['walk_note_zh'], '步行120米到达目的地')
        self.assertEqual(result['segments'][0]['walk_note_en'], 'Walk 120 m to arrive at your destination')

    def test_unknown_instruction_keeps_english_for_the_rest(self):
        # 一个片段翻不出，不再让整条指引退回中文：能翻的翻，剩下的原样保留（不猜义）。
        payload = deepcopy(WALK)
        payload['route']['paths'][0]['steps'] = [{'instruction': '步行120米右转'},
                                                 {'instruction': '穿过广场后询问工作人员'}]
        result, _ = self.compute(payload)
        self.assertIn('穿过广场后询问工作人员', result['segments'][0]['walk_note_zh'])
        self.assertEqual(result['segments'][0]['walk_note_en'],
                         'Walk 120 m, turn right; 穿过广场后询问工作人员')
        # 一句都翻不出来时才留空，避免英文行退化成中文的重复。
        payload['route']['paths'][0]['steps'] = [{'instruction': '穿过广场后询问工作人员'}]
        result, _ = self.compute(payload)
        self.assertIsNone(result['segments'][0]['walk_note_en'])

if __name__ == '__main__':
    unittest.main()
