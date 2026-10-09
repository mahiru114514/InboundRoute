import unittest
from copy import deepcopy
from modules.offline_kit.service import OfflineKitService
from modules.offline_kit.package import OfflinePackager

class OfflineTimelineTests(unittest.TestCase):
    def make_service(self):
        service=object.__new__(OfflineKitService)
        service.packager=OfflinePackager()
        service._station_provider=lambda _: None
        service.trip={'version':1,'days':[{'day_index':1,'ordered_stops':[{
            'stop_id':'s','stop_type':'hotel','arrival_at':0,'departure_at':60,
            'transit_from_previous':{'duration_seconds':0}}]}]}
        service._fetch_trip=lambda _: service.trip
        return service

    def test_zero_timestamps_are_complete(self):
        service=self.make_service()
        self.assertEqual(service.generate('t')['payload']['days'][0]['stops'][0]['arrival_at'],0)

    def test_missing_anchor_times_or_routes_are_rejected(self):
        for field in ['arrival_at','departure_at','transit_from_previous']:
            with self.subTest(field=field):
                service=self.make_service()
                service.trip['days'][0]['ordered_stops'][0][field]=None
                with self.assertRaisesRegex(ValueError,'Day 1'):
                    service.generate('t')

    def test_required_return_transfer_cannot_be_omitted(self):
        service=self.make_service()
        service.trip['anchor_hotel']={'type':'hotel','name_zh':'酒店','name_en':'Hotel',
            'coordinate':{'lat':31.2,'lng':121.4,'crs':'WGS84'}}
        with self.assertRaisesRegex(ValueError,'终点'):
            service.generate('t')

    def test_empty_day_with_different_points_requires_transfer(self):
        service=self.make_service()
        point=lambda name,lat:{'type':'hotel','name_zh':name,'name_en':name,
            'coordinate':{'lat':lat,'lng':121.4,'crs':'WGS84'}}
        day=service.trip['days'][0];day['ordered_stops']=[]
        day.update(start_anchor=point('A',31.2),end_anchor=point('B',31.3))
        with self.assertRaisesRegex(ValueError,'终点'):
            service.generate('t')
        day['end_transit']={'mode':'walk','duration_seconds':600,'to':{'name_zh':'B','name_en':'B'}}
        payload=service.generate('t')['payload']['days'][0]
        self.assertEqual(payload['end_transfer']['duration_seconds'],600)

    def test_return_leg_and_rest_stops_survive_packaging(self):
        service=self.make_service();day=service.trip['days'][0]
        day['ordered_stops'][0].update(hotel_stay_kind='rest',planned_dwell_minutes=1)
        day['end_transit']={'mode':'walk','duration_seconds':600,'data_source':'mock',
            'to':{'name_zh':'机场','name_en':'Airport'},'segments':[{'kind':'walk',
                'distance_meters':400,'walk_note_zh':'沿路直行','walk_note_en':'Go straight'}]}
        payload=service.generate('t')['payload']['days'][0]
        self.assertEqual(payload['stops'][0]['hotel_stay_kind'],'rest')
        self.assertEqual(payload['stops'][0]['planned_dwell_minutes'],1)
        self.assertEqual(payload['end_transfer']['name_zh'],'机场')
        self.assertEqual(payload['end_transfer']['mode'],'walk')
        self.assertEqual(payload['end_transfer']['data_source'],'mock')
        self.assertTrue(payload['end_transfer']['ask_cards'])
        self.assertEqual(payload['end_transfer']['walk_segments'][0]['note_en'],'Go straight')
