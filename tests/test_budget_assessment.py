import unittest, tempfile
from pathlib import Path
from copy import deepcopy
from tests.test_trip_engine import TripService, new_trip_payload, BUND

class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=TripService(Path(self.tmp.name))
        self.trip=self.service.create_trip(new_trip_payload(budget={'scope':'per_person','currency':'CNY','amount_cents':100000}))

    def complete_inputs(self):
        return {'travelers':2,'taxi_vehicles':1,'intercity_cents':10000,
            'lodging_nights':[{'date':'2026-10-12','hotel_name':'酒店','room_price_cents':40000,'rooms':1}],
            'ticket_cents':{},'meal_daily_cents':5000,'meal_overrides':{},'extras_cents':0,'contingency_percent':0}

    def route(self,mode='taxi',source='amap',low=100,high=120):
        return {'mode':mode,'data_source':source,'duration_seconds':600,'cost':{'min':low,'max':high,'currency':'CNY'},
            'variants':[{'mode':'transit','data_source':'amap','duration_seconds':1200,'cost':{'min':5,'max':6,'currency':'CNY'}}]}

    def assess(self,trip,inputs):
        from core.budget_assessment import assess_trip, itinerary_key
        trip={**trip,'cost_inputs':{**inputs,'itinerary_key':itinerary_key(trip)}}
        return assess_trip(trip)

    def test_all_categories_shared_costs_and_tail(self):
        trip=deepcopy(self.trip);trip['days'][0]['end_transit']=self.route()
        a=self.assess(trip,self.complete_inputs())
        self.assertTrue(a['complete'],a['missing'])
        self.assertEqual(a['total'],{'min_cents':45000,'max_cents':46000})
        self.assertEqual(a['status'],'within_budget')
        suggestion=next(s for s in a['suggestions'] if s['kind']=='transit')
        self.assertEqual(suggestion['savings_min_cents'],4400)
        self.assertEqual(suggestion['extra_minutes'],10)

    def test_unknown_or_mock_is_not_free(self):
        a=self.trip.get('budget_assessment')
        self.assertIsNotNone(a)
        self.assertFalse(a['complete']);self.assertEqual(a['status'],'incomplete')
        trip=deepcopy(self.trip);trip['days'][0]['end_transit']=self.route(source='mock')
        a=self.assess(trip,self.complete_inputs())
        self.assertFalse(a['complete']);self.assertTrue(any('演示' in m['message'] for m in a['missing']))

    def test_range_classification_zero_and_missing_still_over(self):
        trip=deepcopy(self.trip);trip['days'][0]['end_transit']=self.route()
        inputs=self.complete_inputs();trip['budget']['amount_cents']=45500
        self.assertEqual(self.assess(trip,inputs)['status'],'at_risk')
        trip['budget']['amount_cents']=44000
        self.assertEqual(self.assess(trip,inputs)['status'],'over_budget')
        inputs['intercity_cents']=None
        trip['budget']['amount_cents']=0
        a=self.assess(trip,inputs);self.assertFalse(a['complete']);self.assertEqual(a['status'],'over_budget')

    def test_repeat_visits_and_explicit_zero_ticket(self):
        trip=deepcopy(self.trip);trip['anchor_arrival']['coordinate']=trip['anchor_hotel']['coordinate']
        day=trip['days'][0]
        day['ordered_stops']=[{'stop_id':s,'stop_type':'poi','poi_id':'same','coordinate':trip['anchor_hotel']['coordinate'],
            'transit_from_previous':self.route('walk',low=0,high=0)} for s in ['first','second']]
        inputs=self.complete_inputs();inputs['lodging_nights']=[];inputs['ticket_cents']={'first':1000,'second':0}
        a=self.assess(trip,inputs)
        self.assertTrue(a['complete'],a['missing']);self.assertEqual(a['categories']['tickets']['min_cents'],1000)
        inputs['ticket_cents']['second']=1000
        self.assertEqual(self.assess(trip,inputs)['categories']['tickets']['min_cents'],2000)

    def test_extra_nights_meal_override_and_contingency(self):
        trip=deepcopy(self.trip);trip['anchor_arrival']['coordinate']=trip['anchor_hotel']['coordinate']
        inputs=self.complete_inputs();inputs['lodging_nights'].append({'date':'2026-10-11','hotel_name':'提前入住','room_price_cents':20000,'rooms':2})
        inputs['meal_overrides']={'2026-10-12':0};inputs['contingency_percent']=10
        a=self.assess(trip,inputs)
        self.assertEqual(a['categories']['lodging']['min_cents'],40000)
        self.assertEqual(a['total'],{'min_cents':60500,'max_cents':60500})

    def test_no_occupancy_assumption_and_stale_itinerary(self):
        trip=deepcopy(self.trip);trip['days'][0]['end_transit']=self.route()
        inputs=self.complete_inputs();inputs['travelers']=None
        a=self.assess(trip,inputs);self.assertFalse(a['complete'])
        self.assertTrue(any('人数' in m['message'] for m in a['missing']))
        inputs=self.complete_inputs();inputs['itinerary_key']='old'
        from core.budget_assessment import assess_trip
        a=assess_trip({**trip,'cost_inputs':inputs})
        self.assertFalse(a['complete']);self.assertTrue(any('行程已变更' in m['message'] for m in a['missing']))
        inputs['intercity_cents']=200000
        a=assess_trip({**trip,'cost_inputs':inputs})
        self.assertEqual(a['status'],'over_budget')
        self.assertTrue(a['stale'])

    def test_inputs_save_reload_and_do_not_clear_routes(self):
        trip=self.service.add_stop(self.trip['trip_id'],2,{'poi_id':BUND})['trip']
        route={**self.route(),'to':{'poi_id':BUND}}
        self.service.patch_trip(trip['trip_id'],{'days':[{'day_index':2,'ordered_stops':[{'stop_order':1,'transit_from_previous':route}]}]})
        updated=self.service.patch_trip(trip['trip_id'],{'cost_inputs':self.complete_inputs()})
        self.assertEqual(updated['cost_inputs']['travelers'],2)
        self.assertEqual(updated['days'][1]['ordered_stops'][0]['transit_from_previous'],route)
        self.assertIn('budget_assessment',self.service.get_trip(trip['trip_id']))
        raw=self.service.store._path(trip['trip_id']).read_text(encoding='utf8')
        self.assertNotIn('budget_assessment',raw)

    def test_tail_persists_and_invalidates_on_reorder(self):
        trip=self.service.add_stop(self.trip['trip_id'],2,{'poi_id':BUND})['trip']
        route={**self.route(),'from':{'poi_id':BUND},'to':{'type':'hotel','name_zh':trip['anchor_hotel']['name_zh']}}
        updated=self.service.patch_trip(trip['trip_id'],{'days':[{'day_index':2,'end_transit':route}]})
        self.assertEqual(self.service.get_trip(trip['trip_id'])['days'][1]['end_transit'],route)
        self.service.reorder_stops(trip['trip_id'],2,{'stop_order':[updated['days'][1]['ordered_stops'][0]['stop_id']]})
        self.assertIsNone(self.service.get_trip(trip['trip_id'])['days'][1]['end_transit'])

    def test_invalid_cost_inputs_rejected(self):
        for inputs in [{'travelers':0},{'travelers':True},{'intercity_cents':-1},{'extras_cents':.5},
                       {'lodging_nights':[{'date':'bad','room_price_cents':3,'rooms':1}]},{'contingency_percent':101}]:
            with self.subTest(inputs=inputs),self.assertRaises(Exception):
                self.service.patch_trip(self.trip['trip_id'],{'cost_inputs':inputs})

    def test_unknown_currency_is_not_assumed_cny(self):
        trip=deepcopy(self.trip)
        route=self.route()
        del route['cost']['currency']
        trip['days'][0]['end_transit']=route
        result=self.assess(trip,self.complete_inputs())
        self.assertFalse(result['complete'])
        self.assertEqual(result['categories']['transport']['min_cents'],0)
        route['cost']['currency']='USD'
        self.assertFalse(self.assess(trip,self.complete_inputs())['complete'])
