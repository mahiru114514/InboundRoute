import tempfile
import unittest
from pathlib import Path
from tests.test_trip_engine import TripService, new_trip_payload, BUND

BUDGET={'scope':'per_person','currency':'CNY','amount_cents':123456}

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=TripService(Path(self.tmp.name))

    def test_create_load_and_duplicate_preserve_per_person_budget(self):
        trip=self.service.create_trip(new_trip_payload(budget=BUDGET))
        self.assertEqual(trip['budget'],BUDGET)
        self.assertEqual(self.service.get_trip(trip['trip_id'])['budget'],BUDGET)
        self.assertEqual(self.service.duplicate_trip(trip['trip_id'])['budget'],BUDGET)

    def test_optional_and_zero_budget_are_distinct(self):
        trip=self.service.create_trip(new_trip_payload())
        self.assertIsNone(trip.get('budget'))
        updated=self.service.patch_trip(trip['trip_id'],{'budget':{**BUDGET,'amount_cents':0}})
        self.assertEqual(updated['budget']['amount_cents'],0)
        self.assertIsNone(self.service.patch_trip(trip['trip_id'],{'budget':None})['budget'])

    def test_budget_update_preserves_timeline_and_route(self):
        trip=self.service.create_trip(new_trip_payload())
        trip=self.service.add_stop(trip['trip_id'],2,{'poi_id':BUND})['trip']
        route={'to':{'poi_id':BUND},'duration_seconds':30}
        self.service.patch_trip(trip['trip_id'],{'days':[{'day_index':2,'ordered_stops':[
            {'stop_order':1,'transit_from_previous':route,'arrival_at':100,'departure_at':200}]}]})
        updated=self.service.patch_trip(trip['trip_id'],{'budget':BUDGET})
        stop=updated['days'][1]['ordered_stops'][0]
        self.assertEqual((stop['arrival_at'],stop['departure_at']),(100,200))
        self.assertEqual(stop['transit_from_previous'],route)

    def test_invalid_budget_rejected_on_create_and_update(self):
        trip=self.service.create_trip(new_trip_payload())
        invalid=[{},True,123,{'amount_cents':1},{**BUDGET,'scope':'total'},
                 {**BUDGET,'currency':'USD'},{**BUDGET,'amount_cents':-1},
                 {**BUDGET,'amount_cents':1.2},{**BUDGET,'amount_cents':True},
                 {**BUDGET,'amount_cents':1000000000000},{**BUDGET,'extra':1}]
        for budget in invalid:
            with self.subTest(budget=budget):
                with self.assertRaisesRegex(Exception,'budget'):
                    self.service.create_trip(new_trip_payload(budget=budget))
                with self.assertRaisesRegex(Exception,'budget'):
                    self.service.patch_trip(trip['trip_id'],{'budget':budget})
        self.assertEqual(self.service.get_trip(trip['trip_id'])['version'],trip['version'])
