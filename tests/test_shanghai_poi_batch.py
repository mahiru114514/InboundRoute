"""第二批真实地点：来源可追溯，未知运营政策不得填默认结论。"""
import json
import tempfile
import unittest
from pathlib import Path
from modules.trip_engine.poi_seed import POIS
from tests.test_poi_crs import gcj02_from_wgs84, metres

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = {f'sh_poi_{i:05}' for i in range(141, 161)}

class ShanghaiPoiBatchTests(unittest.TestCase):
    def test_every_default_poi_validates_against_bundled_contract(self):
        import sys
        from jsonschema import Draft202012Validator
        sys.path.insert(0, str(ROOT/'contracts/scripts'))
        from _bundle import Contracts
        validator = Draft202012Validator(Contracts(ROOT/'contracts').bundled['poi.schema.json'])
        errors = [(p['poi_id'], e.message) for p in POIS for e in validator.iter_errors(p)]
        self.assertEqual(errors, [])

    def test_twenty_new_places_with_city_and_suburban_coverage(self):
        self.assertGreaterEqual(len(POIS), 45)
        by_id = {p['poi_id']: p for p in POIS}
        self.assertTrue(NEW_IDS <= by_id.keys())
        new = [by_id[i] for i in NEW_IDS]
        for district in ['松江区', '嘉定区', '青浦区', '奉贤区', '浦东新区']:
            self.assertTrue(any(district in p['tags'] for p in new), district)
        self.assertEqual({p['category']['level1'] for p in new},
                         {'history_culture', 'local_life', 'modern_skyline', 'nature'})

    def test_all_coordinates_return_to_the_recorded_provider_point(self):
        audit = json.loads((ROOT/'modules/trip_engine/data/shanghai_poi_reviews_v2.json').read_text(encoding='utf-8'))
        reviews = {r['poi_id']: r for r in audit['reviews']}
        by_id = {p['poi_id']: p for p in POIS}
        self.assertEqual(set(reviews), NEW_IDS)
        for pid in NEW_IDS:
            with self.subTest(poi=pid):
                p, r = by_id[pid], reviews[pid]
                self.assertEqual(r['reviewed_on'], '2026-10-04')
                self.assertIn('amap.com/place/', r['coordinate_source'])
                self.assertTrue(r['address'].startswith('上海市'))
                self.assertIn(p['provider_refs']['amap'], r['provider_venue_source'])
                lat, lng = gcj02_from_wgs84(p['coordinate']['lat'], p['coordinate']['lng'])
                self.assertLess(metres(lat, lng, r['gcj02']['lat'], r['gcj02']['lng']), 3)
                self.assertNotIn('precision_m', p['coordinate'], '转换误差不能冒充实地入口精度')

    def test_unknown_hours_booking_and_lighting_are_not_invented(self):
        audit = json.loads((ROOT/'modules/trip_engine/data/shanghai_poi_reviews_v2.json').read_text(encoding='utf-8'))
        by_id = {p['poi_id']: p for p in POIS}
        for r in audit['reviews']:
            rules = by_id[r['poi_id']]['operating_rules']
            with self.subTest(poi=r['poi_id']):
                self.assertIsNone(rules['light_up'])
                self.assertEqual(rules['closure_data_status'], 'unverified')
                self.assertEqual(rules['closure_rules'], [])
                self.assertEqual(by_id[r['poi_id']]['drop_off_locations'], [])
                if not r['verified_operating_fields']:
                    self.assertEqual(rules['opening_hours'], [])
                    self.assertNotIn('reservation_required', rules)
                self.assertIn('停留时长为规划参考', by_id[r['poi_id']]['tags'])

    def test_two_museum_branches_and_current_official_times_are_distinct(self):
        by_id = {p['poi_id']: p for p in POIS}
        self.assertEqual(by_id['sh_poi_00088']['names']['zh-Hans'], '上海博物馆')
        east = by_id['sh_poi_00141']
        self.assertEqual(east['names']['zh-Hans'], '上海博物馆东馆')
        self.assertGreater(metres(east['coordinate']['lat'],east['coordinate']['lng'],
                                by_id['sh_poi_00088']['coordinate']['lat'],by_id['sh_poi_00088']['coordinate']['lng']),3000)
        self.assertEqual(east['operating_rules']['opening_hours'][0]['open'], '10:00')
        self.assertEqual(east['operating_rules']['last_entry_time'], '17:00')
        self.assertFalse(east['operating_rules']['reservation_required'])
        expo = by_id['sh_poi_00144']['operating_rules']
        self.assertEqual(expo['last_entry_time'], '16:15')
        self.assertEqual(expo['opening_hours'][0]['close'], '17:00', '不能沿用已结束的暑期夜场')

    def test_natural_museum_uses_new_site_and_no_conflicting_closed_day(self):
        natural = next(p for p in POIS if p['poi_id']=='sh_poi_00142')
        lat, lng = gcj02_from_wgs84(natural['coordinate']['lat'],natural['coordinate']['lng'])
        self.assertLess(metres(lat,lng,31.235021,121.462672),3)
        self.assertEqual(natural['operating_rules']['closure_rules'], [])

    def test_coordinate_hint_tool_agrees_with_the_production_conversion(self):
        from tools.check_poi_crs import wgs84_from_gcj02
        from modules.route_adapter.crs import wgs84_to_gcj02
        lat,lng = wgs84_from_gcj02(31.235021,121.462672)
        glat,glng = wgs84_to_gcj02(lat,lng)
        self.assertLess(metres(glat,glng,31.235021,121.462672),3,
                        '维护工具不能把新坐标转成与生产地图不一致的WGS84')

    def test_default_store_exposes_new_places_but_custom_catalog_stays_authoritative(self):
        from modules.trip_engine.store import TripStore
        with tempfile.TemporaryDirectory() as directory:
            store = TripStore(Path(directory)/'default')
            self.assertGreaterEqual(len(store.list_pois()),45)
            self.assertTrue(any(p['poi_id']=='sh_poi_00141' for p in store.list_pois(interest='history_culture')))
            custom = Path(directory)/'custom.json'
            custom.write_text(json.dumps([POIS[0]],ensure_ascii=False),encoding='utf-8')
            self.assertEqual(len(TripStore(Path(directory)/'override',custom).list_pois()),1)

if __name__=='__main__':
    unittest.main()
