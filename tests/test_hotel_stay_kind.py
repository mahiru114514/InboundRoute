"""酒店中途休息、过夜继承和旧停靠点兼容。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tests.test_trip_engine import TripService, new_trip_payload, BUND
from modules.trip_engine.errors import EngineError


class HotelStayKindTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = TripService(Path(temporary.name))
        self.trip = self.service.create_trip(new_trip_payload(duration_days=3))
        self.hotel = {**deepcopy(self.trip['anchor_hotel']), 'type':'hotel', 'name_zh':'另一家酒店'}

    def add_hotel(self, kind=None, **extra):
        payload = {'stop_type':'hotel', 'anchor':self.hotel, 'planned_dwell_minutes':60, **extra}
        if kind is not None:
            payload['hotel_stay_kind'] = kind
        return self.service.add_stop(self.trip['trip_id'], 1, payload)['trip']

    def test_rest_can_be_inserted_and_does_not_change_overnight_or_next_day(self):
        self.service.add_stop(self.trip['trip_id'], 1, {'poi_id':BUND})
        trip = self.add_hotel('rest', stop_order=1)
        self.assertEqual(trip['days'][0]['ordered_stops'][0].get('hotel_stay_kind'), 'rest')
        self.assertEqual(trip['days'][0]['ordered_stops'][1]['poi_id'], BUND)
        self.assertEqual(trip['resolved_day_points'][1]['end']['name_zh'], self.trip['anchor_hotel']['name_zh'])
        self.assertEqual(trip['resolved_day_points'][2]['start']['name_zh'], self.trip['anchor_hotel']['name_zh'])
        self.assertEqual([n['hotel_name'] for n in trip['budget_assessment']['defaults']['lodging_nights']],
                         [self.trip['anchor_hotel']['name_zh']] * 2)

    def test_overnight_and_legacy_stops_keep_hotel_inheritance(self):
        for kind in ('overnight', None):
            with self.subTest(kind=kind):
                trip = self.add_hotel(kind)
                self.assertEqual(trip['resolved_day_points'][2]['start']['name_zh'], self.hotel['name_zh'])

    def test_invalid_stay_kind_or_non_hotel_kind_is_rejected_without_write(self):
        original = self.service.get_trip(self.trip['trip_id'])
        for payload in ({'stop_type':'hotel','hotel_stay_kind':'booking'},
                        {'poi_id':BUND,'hotel_stay_kind':'rest'},
                        {'stop_type':'arrival_anchor','hotel_stay_kind':'overnight'}):
            with self.subTest(payload=payload), self.assertRaises(EngineError):
                self.service.add_stop(self.trip['trip_id'], 1, payload)
        self.assertEqual(self.service.get_trip(self.trip['trip_id']), original)

    def test_remove_rest_point_preserves_other_stops_and_hotel(self):
        self.service.add_stop(self.trip['trip_id'], 1, {'poi_id':BUND})
        trip = self.add_hotel('rest', stop_order=1)
        rest_id = trip['days'][0]['ordered_stops'][0]['stop_id']
        trip = self.service.remove_stop(trip['trip_id'], 1, rest_id)['trip']
        self.assertEqual([s['poi_id'] for s in trip['days'][0]['ordered_stops']], [BUND])
        self.assertEqual(trip['resolved_day_points'][2]['start']['name_zh'], self.trip['anchor_hotel']['name_zh'])


if __name__ == '__main__':
    unittest.main()
