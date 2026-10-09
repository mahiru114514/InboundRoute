"""整批推荐必须原子保存、保护用户编辑，并验证版本。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from modules.trip_engine.errors import EngineError
from modules.trip_engine.service import TripService
from tests.test_trip_engine import new_trip_payload, BUND, MUSEUM


def plan(*days):
    return {'plan': {'days': [
        {'day_index': index, 'stops': [{'poi_id': poi, 'planned_dwell_minutes': 90} for poi in pois]}
        for index, pois in days
    ]}}


class RecommendationApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = TripService(Path(self.tmp.name))
        self.setup = new_trip_payload(duration_days=5)

    def test_preview_does_not_persist(self):
        self.assertTrue(hasattr(self.service, 'preview_trip'), '缺少只读骨架预览')
        result = self.service.preview_trip(self.setup)
        self.assertEqual(len(result['days']), 5)
        self.assertEqual(self.service.store.list_trips(), [])

    def test_create_complete_recommendation_with_editable_stops(self):
        self.assertTrue(hasattr(self.service, 'create_recommended_trip'), '缺少原子推荐创建')
        result = self.service.create_recommended_trip({'setup':self.setup, **plan((2,[BUND]), (3,[MUSEUM]))})
        self.assertEqual(len(self.service.store.list_trips()), 1)
        self.assertEqual(result['version'], 1)
        self.assertEqual(result['days'][0]['ordered_stops'], [])
        self.assertEqual(result['days'][4]['ordered_stops'], [])
        stop = result['days'][1]['ordered_stops'][0]
        self.assertEqual(stop['poi_id'], BUND)
        self.assertFalse(stop['locked'])
        self.assertTrue(stop['stop_id'].startswith('stop_'))
        edited = self.service.remove_stop(result['trip_id'], 2, stop['stop_id'])['trip']
        self.assertEqual(edited['days'][1]['ordered_stops'], [])

    def test_invalid_last_poi_does_not_leave_new_trip(self):
        self.assertTrue(hasattr(self.service, 'create_recommended_trip'))
        with self.assertRaises(EngineError):
            self.service.create_recommended_trip({'setup':self.setup, **plan((2,[BUND]), (3,['missing']))})
        self.assertEqual(self.service.store.list_trips(), [])

    def test_existing_batch_commits_one_version_and_keeps_anchors(self):
        self.assertTrue(hasattr(self.service, 'apply_recommendations'), '缺少推荐批量写入')
        trip = self.service.create_trip(self.setup)
        result = self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND]), (3,[MUSEUM])), 1)
        self.assertEqual(result['version'], 2)
        self.assertEqual(len(result['revision_history']), 2)
        for key in ('anchor_hotel','anchor_arrival','anchor_departure'):
            self.assertEqual(result[key], trip[key])

    def test_failure_does_not_partially_change_existing_trip(self):
        self.assertTrue(hasattr(self.service, 'apply_recommendations'))
        trip = self.service.create_trip(self.setup)
        before = self.service.get_trip(trip['trip_id'])
        with self.assertRaises(EngineError):
            self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND]), (3,['missing'])), 1)
        self.assertEqual(self.service.get_trip(trip['trip_id']), before)

    def test_locked_or_nonempty_day_cannot_be_overwritten(self):
        self.assertTrue(hasattr(self.service, 'apply_recommendations'))
        trip = self.service.create_trip(self.setup)
        trip = self.service.add_stop(trip['trip_id'], 2, {'poi_id':BUND, 'locked':True})['trip']
        before = self.service.get_trip(trip['trip_id'])
        with self.assertRaises(EngineError):
            self.service.apply_recommendations(trip['trip_id'], plan((2,[MUSEUM])), trip['version'])
        self.assertEqual(self.service.get_trip(trip['trip_id']), before)

    def test_poi_cannot_repeat_across_existing_and_generated_days(self):
        self.assertTrue(hasattr(self.service, 'apply_recommendations'))
        trip = self.service.create_trip(self.setup)
        trip = self.service.add_stop(trip['trip_id'], 1, {'poi_id':BUND})['trip']
        with self.assertRaises(EngineError):
            self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND])), trip['version'])
        with self.assertRaises(EngineError):
            self.service.apply_recommendations(trip['trip_id'], plan((2,[MUSEUM]), (3,[MUSEUM])), trip['version'])

    def test_empty_locked_day_cannot_receive_recommendation(self):
        trip = self.service.create_trip(self.setup)
        trip['days'][1]['day_status'] = 'locked'
        self.service.store.save(trip)
        before = self.service.get_trip(trip['trip_id'])
        with self.assertRaises(EngineError):
            self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND])), before['version'])
        self.assertEqual(self.service.get_trip(trip['trip_id']), before)

    def test_applying_other_day_preserves_empty_locked_day(self):
        trip = self.service.create_trip(self.setup)
        trip['days'][2]['day_status'] = 'locked'
        self.service.store.save(trip)
        before = self.service.store.get(trip['trip_id'])
        result = self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND])), before['version'])
        self.assertEqual(before['days'][2]['day_status'], 'locked')
        self.assertEqual(result['days'][2], before['days'][2])

    def test_version_is_required_and_stale_version_cannot_apply_twice(self):
        self.assertTrue(hasattr(self.service, 'apply_recommendations'))
        trip = self.service.create_trip(self.setup)
        for value in (None, '', 'abc', True, 0, 1.5):
            with self.subTest(version=value), self.assertRaises(EngineError):
                self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND])), value)
        self.service.apply_recommendations(trip['trip_id'], plan((2,[BUND])), 1)
        with self.assertRaises(EngineError) as context:
            self.service.apply_recommendations(trip['trip_id'], plan((3,[MUSEUM])), 1)
        self.assertEqual(context.exception.status, 409)

    def test_bad_plan_fields_and_empty_results_are_rejected(self):
        self.assertTrue(hasattr(self.service, 'create_recommended_trip'))
        bad = [
            {'days':[]},
            {'days':[{'day_index':2,'stops':[]}]},
            {'days':[{'day_index':2,'stops':[]},{'day_index':2,'stops':[]}]},
            {'days':[{'day_index':True,'stops':[{'poi_id':BUND}]}]},
            {'days':[{'day_index':6,'stops':[{'poi_id':BUND}]}]},
            {'days':[{'day_index':2,'stops':[{'poi_id':BUND,'planned_dwell_minutes':True}]}]},
            {'days':[{'day_index':2,'stops':[{'poi_id':BUND,'planned_dwell_minutes':721}]}]},
            {'days':[{'day_index':2,'stops':[{'poi_id':BUND,'locked':True}]}]},
        ]
        for value in bad:
            with self.subTest(plan=value), self.assertRaises(EngineError):
                self.service.create_recommended_trip({'setup':self.setup,'plan':deepcopy(value)})
        self.assertEqual(self.service.store.list_trips(), [])


if __name__ == '__main__':
    unittest.main()
