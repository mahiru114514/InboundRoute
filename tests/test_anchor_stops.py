import unittest
from pathlib import Path
import tempfile
from tests.test_trip_engine import TripService, new_trip_payload, BUND

class AnchorStopsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = TripService(Path(self.tmp.name))
        self.trip = self.service.create_trip(new_trip_payload())

    def add(self, kind='hotel', **extra):
        return self.service.add_stop(self.trip['trip_id'], 1, {'stop_type': kind, **extra})['trip']

    def test_mixed_stops_have_stable_ids_and_can_reorder_remove_individually(self):
        trip = self.add()
        trip = self.add()
        stops = trip['days'][0]['ordered_stops']
        ids = [s['stop_id'] for s in stops]
        self.assertNotEqual(*ids)
        self.assertTrue(all(s['poi_id'] is None for s in stops))
        trip = self.service.reorder_stops(trip['trip_id'], 1, {'stop_order': ids[::-1]})['trip']
        self.assertEqual([s['stop_id'] for s in trip['days'][0]['ordered_stops']], ids[::-1])
        trip = self.service.remove_stop(trip['trip_id'], 1, ids[0])['trip']
        self.assertEqual([s['stop_id'] for s in trip['days'][0]['ordered_stops']], [ids[1]])

    def test_anchor_insert_and_hotel_inheritance(self):
        self.service.add_stop(self.trip['trip_id'], 1, {'poi_id': BUND})
        hotel = {**self.trip['anchor_hotel'], 'type': 'hotel', 'name_zh': '新酒店'}
        trip = self.add(anchor=hotel, stop_order=1, planned_dwell_minutes=480)
        self.assertEqual(trip['days'][0]['ordered_stops'][0]['name_zh'], '新酒店')
        self.assertEqual(trip['resolved_day_points'][2]['start']['name_zh'], '新酒店')
        self.assertEqual(trip['days'][0]['day_status'], 'partial')

    def test_lock_and_unlock_refresh_status(self):
        trip = self.service.add_stop(self.trip['trip_id'], 1, {'poi_id': BUND})['trip']
        self.assertEqual(trip['days'][0]['day_status'], 'partial')
        trip = self.service.patch_trip(trip['trip_id'], {'days': [{'day_index': 1, 'ordered_stops': [{'stop_order': 1, 'locked': True}]}]})
        self.assertEqual(trip['days'][0]['day_status'], 'locked')
        trip = self.service.patch_trip(trip['trip_id'], {'days': [{'day_index': 1, 'ordered_stops': [{'stop_order': 1, 'locked': False}]}]})
        self.assertEqual(trip['days'][0]['day_status'], 'partial')

    def test_port_and_hotel_share_timeline_chain(self):
        from modules.rules_engine.rules import build_timeline
        trip = self.add('arrival_anchor')
        trip = self.add(planned_dwell_minutes=480)
        day = trip['days'][0]
        for stop in day['ordered_stops']:
            stop['transit_from_previous'] = {'duration_seconds': 600}
        times = build_timeline(trip, day)
        self.assertEqual(times[1]['arrival_at'], times[0]['departure_at'] + 600)
        self.assertEqual(times[1]['departure_at'] - times[1]['arrival_at'], 480 * 60)

    def test_hotel_change_invalidates_following_day_transport(self):
        trip=self.service.add_stop(self.trip['trip_id'],2,{'poi_id':BUND})['trip']
        self.service.patch_trip(trip['trip_id'],{'days':[{'day_index':2,'ordered_stops':[
            {'stop_order':1,'transit_from_previous':{'to':{'poi_id':BUND},'duration_seconds':30},'arrival_at':100,'departure_at':200}]}]})
        hotel={**trip['anchor_hotel'],'type':'hotel','name_zh':'新酒店'}
        trip=self.add(anchor=hotel)
        self.assertIsNone(trip['days'][1]['ordered_stops'][0]['transit_from_previous'])

    def test_explicit_arrival_stop_starts_at_actual_arrival(self):
        from modules.rules_engine.rules import build_timeline
        trip=self.add('arrival_anchor',stop_order=1)
        day=trip['days'][0]
        day['ordered_stops'][0]['transit_from_previous']={'duration_seconds':0}
        times=build_timeline(trip,day)
        self.assertEqual(times[0]['arrival_at'],trip['anchor_arrival']['at'])
        self.assertEqual(times[0]['departure_at'],trip['anchor_arrival']['activity_start_at'])

if __name__ == '__main__': unittest.main()
