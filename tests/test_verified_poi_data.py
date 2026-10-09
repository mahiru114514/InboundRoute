"""Officially reviewed facts must reach the seed used by the running service."""
import json
import unittest
from pathlib import Path
from modules.trip_engine.poi_seed import POIS

ROOT = Path(__file__).resolve().parents[1]

class VerifiedPoiTests(unittest.TestCase):
    def test_museum_daytime_and_booking_scope(self):
        museum = next(p for p in POIS if p['poi_id'] == 'sh_poi_00088')
        self.assertEqual(museum['operating_rules']['last_entry_time'], '15:00')
        self.assertIsNone(museum['operating_rules']['advance_booking_days'])
        self.assertTrue(any('夜场' in tag for tag in museum['tags']))

    def test_review_record_tracks_scope_and_no_fake_lighting_verification(self):
        records = json.loads((ROOT / 'modules/trip_engine/data/operating_reviews.json').read_text(encoding='utf-8'))
        museum = records['reviews'][0]
        self.assertEqual(museum['poi_id'], 'sh_poi_00088')
        self.assertEqual(museum['verified_fields']['last_entry_time'], '15:00')
        self.assertTrue(museum['source_url'].startswith('https://www.shanghaimuseum.cn/'))
        self.assertEqual(records['lighting_status'], 'demo_windows_not_verified')
