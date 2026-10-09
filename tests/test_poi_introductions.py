"""景点简介主数据、查询入口及契约兼容。"""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from modules.trip_engine.poi_seed import POIS
from modules.trip_engine.service import TripService
from modules.trip_engine.http_api import build_server
from contracts.generated.models import Poi

ROOT = Path(__file__).resolve().parents[1]


class PoiIntroductionTests(unittest.TestCase):
    def test_every_seed_has_short_distinct_introduction(self):
        self.assertEqual(len(POIS), 45)
        for poi in POIS:
            with self.subTest(poi=poi['poi_id']):
                text = poi.get('description_zh', '')
                self.assertIsInstance(text, str)
                self.assertTrue(text.strip(), '缺少景点介绍')
                self.assertEqual(text, text.strip())
                self.assertLessEqual(len(text), 120)
        self.assertEqual(len({p.get('description_zh') for p in POIS}), len(POIS))

    def test_description_sources_cover_every_seed(self):
        path = ROOT / 'modules/trip_engine/data/poi_description_reviews.json'
        self.assertTrue(path.is_file(), '缺少简介审核来源记录')
        audit = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(audit['reviewed_on'], '2026-10-06')
        reviews = {r['poi_id']:r for r in audit['reviews']}
        self.assertEqual(set(reviews), {p['poi_id'] for p in POIS})
        for record in reviews.values():
            self.assertTrue(record['sources'])
            self.assertTrue(all(url.startswith('https://') for url in record['sources']))

    def test_contract_preserves_old_pois_and_bounds_description(self):
        from contracts.generated.schema_store import is_valid
        poi = deepcopy(POIS[0])
        poi.pop('description_zh', None)
        self.assertTrue(is_valid(poi, 'poi.schema.json'))
        poi['description_zh'] = '黄浦江畔散步和欣赏城市景观。'
        self.assertTrue(is_valid(poi, 'poi.schema.json'))
        for invalid in ('', '字' * 121, 123):
            poi['description_zh'] = invalid
            self.assertFalse(is_valid(poi, 'poi.schema.json'))

    def test_generated_poi_model_preserves_introduction(self):
        poi = deepcopy(POIS[0])
        poi['description_zh'] = '沿江散步，欣赏外滩建筑与城市天际线。'
        dumped = Poi.from_dict(poi).to_dict()
        self.assertIn('description_zh', dumped)
        self.assertEqual(dumped['description_zh'], poi['description_zh'])

    def test_http_catalogue_contains_all_descriptions_without_trip_write(self):
        with tempfile.TemporaryDirectory() as directory:
            service = TripService(Path(directory))
            server = build_server(service, 'intro-test-token')
            threading.Thread(target=server.serve_forever, daemon=True).start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request('GET', '/pois', headers={'X-Module-Token':'intro-test-token'})
                response = connection.getresponse()
                body = json.loads(response.read())
                self.assertEqual(response.status, 200, body)
                self.assertEqual(len(body['data']['pois']), 45)
                self.assertTrue(all(p.get('description_zh') for p in body['data']['pois']))
                self.assertEqual(service.store.list_trips(), [])
            finally:
                connection.close()
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
