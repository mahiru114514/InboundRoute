import json
import unittest
from pathlib import Path
from copy import deepcopy
from core.budget_assessment import assess_trip, itinerary_key, validate_cost_inputs

ANCHORS = json.loads((Path(__file__).resolve().parents[1] / 'modules/trip_engine/data/anchors.json').read_text(encoding='utf-8'))

def hotel(hid):
    h = next(h for h in ANCHORS['hotels'] if h['id'] == hid)
    return {'type':'hotel', 'name_zh':h['name_zh'], 'name_en':h['name_en'],
            'coordinate':{'lat':h['lat'], 'lng':h['lng'], 'crs':'WGS84'}}

def trip():
    return {'anchor_hotel':hotel('hotel_peace'), 'days':[
        {'day_index':1,'date':'2026-10-12','ordered_stops':[]},
        {'day_index':2,'date':'2026-10-13','ordered_stops':[]},
        {'day_index':3,'date':'2026-10-14','ordered_stops':[]}], 'cost_inputs':{},
        'budget':{'amount_cents':300000}}

def visit(sid, pid):
    return {'stop_id':sid,'stop_type':'poi','poi_id':pid}

class AutoPricingTests(unittest.TestCase):
    def test_added_removed_and_repeated_ticket_visits(self):
        t=trip(); t['days'][0]['ordered_stops']=[visit('a','sh_poi_00107'),visit('b','sh_poi_00107')]
        self.assertEqual(assess_trip(t)['categories']['tickets']['min_cents'],8000)
        t['days'][0]['ordered_stops'].pop()
        self.assertEqual(assess_trip(t)['categories']['tickets']['min_cents'],4000)
        t['days'][0]['date']='2026-12-12'
        self.assertEqual(assess_trip(t)['categories']['tickets']['min_cents'],3000)

    def test_manual_override_zero_and_blank_return_to_reference(self):
        t=trip(); t['days'][0]['ordered_stops']=[visit('a','sh_poi_00107')]
        for value, expected in [(999,999),(0,0),(None,4000)]:
            t['cost_inputs']['ticket_cents']={'a':value}
            self.assertEqual(assess_trip(t)['categories']['tickets']['min_cents'],expected)

    def test_special_exhibition_base_free_and_unknown_not_free(self):
        t=trip(); t['days'][0]['ordered_stops']=[visit('a','sh_poi_00088'),visit('b','sh_poi_00123')]
        a=assess_trip(t)
        self.assertEqual(a['categories']['tickets']['min_cents'],0)
        self.assertFalse(a['categories']['tickets']['complete'])
        self.assertTrue(any('148' in n['message'] for n in a['price_notices']))
        self.assertEqual(a['defaults']['ticket_prices']['a']['min_cents'],0)
        t['days'][0]['date']='2028-01-01'
        self.assertFalse(any('148' in n['message'] for n in assess_trip(t)['price_notices']))

    def test_auto_room_nights_ranges_and_sharing(self):
        t=trip(); a=assess_trip(t)
        self.assertEqual(a['categories']['lodging']['min_cents'],456000)
        self.assertEqual(a['categories']['lodging']['max_cents'],610000)
        self.assertEqual(len(a['defaults']['lodging_nights']),2)
        self.assertTrue(any('1 人' in n for n in a['assumptions']))
        t['cost_inputs']={'travelers':2,'lodging_rooms':1}
        self.assertEqual(assess_trip(t)['categories']['lodging']['min_cents'],228000)
        t['cost_inputs']['lodging_rooms']=2
        self.assertEqual(assess_trip(t)['categories']['lodging']['min_cents'],456000)

    def test_hotel_stops_change_inherited_nights_without_duplicate_charge(self):
        t=trip(); h=hotel('hotel_jinjiang')
        t['days'][0]['ordered_stops']=[{**h,'stop_type':'hotel','stop_id':'h1'},{**h,'stop_type':'hotel','stop_id':'h2'}]
        a=assess_trip(t)
        self.assertEqual(a['categories']['lodging']['min_cents'],114000)
        self.assertEqual(a['categories']['lodging']['max_cents'],188000)
        t['days'][0]['ordered_stops']=[]
        self.assertEqual(assess_trip(t)['categories']['lodging']['min_cents'],456000)
        t['anchor_hotel']=hotel('hotel_hyland')
        a=assess_trip(t)
        self.assertFalse(a['categories']['lodging']['complete'])
        self.assertEqual(a['categories']['lodging']['min_cents'],0)

    def test_manual_nights_and_explicit_empty_list_remain_authoritative(self):
        t=trip(); t['cost_inputs']={'travelers':2,'lodging_nights':[{'date':'2026-10-11','hotel_name':'自订酒店','rooms':2,'room_price_cents':12345}]}
        self.assertEqual(assess_trip(t)['categories']['lodging']['min_cents'],12345)
        t['cost_inputs']['lodging_nights']=[]
        self.assertEqual(assess_trip(t)['categories']['lodging']['max_cents'],0)

    def test_auto_costs_refresh_even_when_previous_manual_inputs_need_review(self):
        t=trip(); t['cost_inputs']={'itinerary_key':itinerary_key(t),'lodging_nights':None}
        t['anchor_hotel']=hotel('hotel_jinjiang')
        a=assess_trip(t)
        self.assertTrue(a['stale'])
        self.assertEqual(a['categories']['lodging']['min_cents'],114000)
        self.assertEqual(a['lines'][0]['source'],'reference_price')
        self.assertTrue(a['lines'][0]['sources'])

    def test_room_count_validation(self):
        self.assertEqual(validate_cost_inputs({'lodging_rooms':2})['lodging_rooms'],2)
        for value in (0,True,101,1.5):
            with self.assertRaises(ValueError): validate_cost_inputs({'lodging_rooms':value})

    def test_custom_location_does_not_reuse_nearby_hotel_name_price(self):
        t=trip(); t['anchor_hotel']['coordinate']['lat']=31.4
        a=assess_trip(t)
        self.assertFalse(a['categories']['lodging']['complete'])
        self.assertEqual(a['categories']['lodging']['max_cents'],0)

    def test_service_selection_save_reload_change_and_remove(self):
        import tempfile
        from tests.test_trip_engine import TripService, new_trip_payload
        with tempfile.TemporaryDirectory() as directory:
            service=TripService(Path(directory))
            h=hotel('hotel_peace'); h.pop('type')
            t=service.create_trip(new_trip_payload(anchor_hotel=h,duration_days=3))
            t=service.add_stop(t['trip_id'],2,{'poi_id':'sh_poi_00107'})['trip']
            self.assertEqual(t['budget_assessment']['categories']['tickets']['min_cents'],4000)
            t=service.patch_trip(t['trip_id'],{'cost_inputs':{'travelers':2,'lodging_rooms':1,'lodging_nights':None}})
            self.assertEqual(t['budget_assessment']['categories']['lodging']['min_cents'],228000)
            self.assertIsNone(t['cost_inputs']['lodging_nights'])
            t=service.get_trip(t['trip_id'])
            self.assertEqual(t['budget_assessment']['categories']['lodging']['min_cents'],228000)
            h=hotel('hotel_jinjiang'); h.pop('type')
            t=service.patch_trip(t['trip_id'],{'anchor_hotel':h})
            self.assertEqual(t['budget_assessment']['categories']['lodging']['min_cents'],57000)
            service.remove_stop(t['trip_id'],2,t['days'][1]['ordered_stops'][0]['stop_id'])
            t=service.get_trip(t['trip_id'])
            self.assertEqual(t['budget_assessment']['categories']['tickets']['max_cents'],0)
