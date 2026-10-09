import unittest

from core.trip_points import resolve_day_points


def anchor(name, kind='hotel'):
    return {'type': kind, 'name_zh': name, 'name_en': name,
            'coordinate': {'lat': 31.2, 'lng': 121.4, 'crs': 'WGS84'}}


class DayPointsTests(unittest.TestCase):
    def make_trip(self):
        return {'anchor_hotel': anchor('A'),
                'anchor_arrival': {'location_name': '机场', 'coordinate': anchor('A')['coordinate']},
                'anchor_departure': {'location_name': '车站', 'coordinate': anchor('A')['coordinate']},
                'days': [{'day_index': i} for i in range(1, 5)]}

    def test_defaults_and_hotel_change_inherit(self):
        trip = self.make_trip()
        original = resolve_day_points(trip)
        self.assertEqual(original[1]['start']['name_zh'], '机场')
        self.assertEqual(original[4]['end']['name_zh'], '车站')
        trip['days'][1]['end_anchor'] = anchor('B')
        points = resolve_day_points(trip)
        self.assertEqual(points[2]['start']['name_zh'], 'A')
        self.assertEqual(points[2]['end']['name_zh'], 'B')
        self.assertEqual(points[3]['start']['name_zh'], 'B')
        self.assertEqual(points[3]['end']['name_zh'], 'B')
        self.assertEqual(points[4]['start']['name_zh'], 'B')
        self.assertEqual(points[4]['end']['name_zh'], '车站')

    def test_explicit_points_and_restore_defaults(self):
        trip = self.make_trip()
        trip['days'][0]['end_anchor'] = anchor('B')
        trip['days'][1]['start_anchor'] = anchor('C')
        trip['days'][2]['end_anchor'] = anchor('景点', 'poi')
        points = resolve_day_points(trip)
        self.assertEqual(points[2]['end']['name_zh'], 'C')
        self.assertEqual(points[4]['start']['name_zh'], '景点')
        trip['days'][1]['start_anchor'] = None
        self.assertEqual(resolve_day_points(trip)[2]['end']['name_zh'], 'B')

    def test_route_segments_use_daily_points_and_empty_hotel_transfer(self):
        from modules.route_adapter.service import RouteAdapterService
        service = object.__new__(RouteAdapterService)
        trip = self.make_trip()
        trip['days'][1]['end_anchor'] = anchor('B')
        trip['days'][1]['ordered_stops'] = [{'stop_order': 1, 'poi_id': 'poi',
            'name_zh': '景点', 'name_en': 'POI', 'coordinate': anchor('景点')['coordinate']}]
        service._fetch_trip = lambda _: trip
        segments = service._trip_day_segments('isolated', 2)
        self.assertEqual([(a['name_zh'], b['name_zh']) for a, b in segments], [('A', '景点'), ('景点', 'B')])
        trip['days'][1]['ordered_stops'] = []
        segments = service._trip_day_segments('isolated', 2)
        self.assertEqual([(a['name_zh'], b['name_zh']) for a, b in segments], [('A', 'B')])
