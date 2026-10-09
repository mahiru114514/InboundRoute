import copy
import importlib
import unittest

from modules.recommendation_engine.tests.common import at, poi, trip


class PlannerTests(unittest.TestCase):
    def generate(self, *args):
        try:
            planner = importlib.import_module('modules.recommendation_engine.planner')
        except ModuleNotFoundError:
            self.fail('generate_plan implementation is missing')
        return planner.generate_plan(*args)

    def ids(self, result):
        return [stop['poi_id'] for day in result['days'] for stop in day['stops']]

    def test_only_selected_days_and_inputs_unchanged(self):
        value, pois = trip(), [poi(i) for i in range(12)]
        before = copy.deepcopy((value, pois))
        result = self.generate(value, pois, [2, 3, 4])
        self.assertEqual([d['day_index'] for d in result['days']], [2, 3, 4])
        self.assertEqual((value, pois), before)
        self.assertEqual(len(self.ids(result)), len(set(self.ids(result))))
        self.assertEqual(result['trip_version'], 3)

    def test_pacing_caps(self):
        for pacing, cap in [('relaxed', 2), ('balanced', 4), ('packed', 6)]:
            with self.subTest(pacing=pacing):
                result = self.generate(trip(pacing), [poi(i) for i in range(10)], [2])
                self.assertEqual(len(self.ids(result)), cap)

    def test_interest_changes_first_choice(self):
        pois = [poi(1, 'nature'), poi(2, 'history_culture')]
        nature = self.generate(trip(interests=['nature']), pois, [2])
        culture = self.generate(trip(interests=['history_culture']), pois, [2])
        self.assertEqual(self.ids(nature)[0], pois[0]['poi_id'])
        self.assertEqual(self.ids(culture)[0], pois[1]['poi_id'])
        self.assertTrue(nature['days'][0]['stops'][0]['reasons'])

    def test_nearby_cluster_preferred_to_remote(self):
        result = self.generate(trip('relaxed'), [poi(1, lng=121.9), poi(2), poi(3, lng=121.48)], [2])
        self.assertEqual(set(self.ids(result)), {'sh_poi_00002', 'sh_poi_00003'})

    def test_weekly_closure_and_open_exception(self):
        item = poi(1)
        item['operating_rules']['closure_rules'] = [{'kind': 'weekly', 'weekday': 1}]
        self.assertEqual(self.ids(self.generate(trip(), [item], [2])), [])
        item['operating_rules']['closure_rules'].append({'kind': 'holiday_exception_open', 'date': '2026-10-05'})
        self.assertEqual(self.ids(self.generate(trip(), [item], [2])), ['sh_poi_00001'])

    def test_special_closure_excludes_candidate(self):
        item = poi(1)
        item['operating_rules']['closure_rules'] = [{'kind': 'maintenance', 'date_from': '2026-10-04', 'date_to': '2026-10-08'}]
        self.assertEqual(self.ids(self.generate(trip(), [item, poi(2)], [2])), ['sh_poi_00002'])

    def test_existing_and_locked_days_skipped_and_existing_poi_not_repeated(self):
        value = trip()
        value['days'][1]['ordered_stops'] = [{'poi_id': 'sh_poi_00001', 'stop_type': 'poi', 'locked': True}]
        value['days'][2]['day_status'] = 'locked'
        result = self.generate(value, [poi(1), poi(2)], [2, 3, 4])
        self.assertEqual([d['day_index'] for d in result['skipped_days']], [2, 3])
        self.assertEqual(self.ids(result), ['sh_poi_00002'])

    def test_invalid_indices_rejected(self):
        for indices in [[], [2, 2], [True], ['2'], [0], [6], None]:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                self.generate(trip(), [poi(1)], indices)

    def test_missing_data_and_reservation_are_honest(self):
        item = poi(1)
        item['operating_rules'] = {'closure_data_status': 'unknown', 'reservation_required': True}
        result = self.generate(trip(), [item], [2])
        warnings = ' '.join(result['warnings'] + result['days'][0]['stops'][0]['warnings'])
        self.assertIn('核验', warnings)
        self.assertIn('预约', warnings)
        self.assertIn('估算', warnings)
        self.assertIn('预算', warnings)

    def test_opening_window_and_dwell_must_fit(self):
        item = poi(1, dwell=90)
        item['operating_rules']['opening_hours'] = [{'open': '09:00', 'close': '10:00'}]
        result = self.generate(trip(), [item, poi(2)], [2])
        self.assertEqual(self.ids(result), ['sh_poi_00002'])
        self.assertTrue(result['warnings'])

    def test_last_entry_and_season_weekday_windows(self):
        item = poi(1)
        item['operating_rules']['last_entry_time'] = '08:30'
        second = poi(2)
        second['operating_rules']['opening_hours'] = [{'open': '09:00', 'close': '22:00', 'weekdays': [2]}]
        third = poi(3)
        third['operating_rules']['opening_hours'] = [{'open': '09:00', 'close': '22:00', 'date_from': '05-01', 'date_to': '09-30'}]
        self.assertEqual(self.ids(self.generate(trip(), [item, second, third], [2])), [])

    def test_actual_arrival_and_departure_boundaries(self):
        value = trip()
        value['anchor_arrival']['activity_start_at'] = at('2026-10-04', '21:30')
        value['anchor_departure']['at'] = at('2026-10-08', '10:00')
        result = self.generate(value, [poi(1)], [1, 5])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(len(result['skipped_days']), 2)

    def test_daily_start_and_distance_reserve_limit_count(self):
        value = trip('packed')
        value['days'][1]['daily_start_local'] = '19:45'
        result = self.generate(value, [poi(i, dwell=90) for i in range(6)], [2])
        self.assertEqual(len(self.ids(result)), 1)

    def test_exhaustion_returns_actual_content_then_skips(self):
        result = self.generate(trip(), [poi(1)], [2, 3])
        self.assertEqual(self.ids(result), ['sh_poi_00001'])
        self.assertEqual(result['skipped_days'][0]['day_index'], 3)
        self.assertTrue(result['skipped_days'][0]['reason'])

    def test_party_affects_range_dwell_and_daily_rest(self):
        value = trip('packed')
        value['days'][1]['daily_start_local'] = '17:00'
        items = [poi(i) for i in range(6)]
        for item in items:
            item['operating_rules']['dwell_time'] = {'kind': 'range', 'minutes_min': 60, 'minutes_max': 100}
        solo = self.generate(value, items, [2])
        value['user_profile']['party_composition'] = 'senior'
        seniors = self.generate(value, items, [2])
        self.assertGreater(len(self.ids(solo)), len(self.ids(seniors)))
        self.assertEqual(seniors['days'][0]['stops'][0]['planned_dwell_minutes'], 100)

    def test_daily_start_anchor_changes_nearest_choice(self):
        value = trip('relaxed')
        value['days'][1]['start_anchor'] = {'type': 'hotel', 'coordinate': {'lat': 31.23, 'lng': 121.8, 'crs': 'WGS84'}}
        result = self.generate(value, [poi(1), poi(2, lng=121.8)], [2])
        self.assertEqual(self.ids(result)[0], 'sh_poi_00002')

    def test_required_light_up_prefers_evening_window(self):
        item = poi(1)
        item['operating_rules']['light_up'] = {'required': True, 'T_light_rule': 'window_start',
            'windows': [{'date_from': '01-01', 'date_to': '12-31', 'start': '19:00', 'close': '21:00'}]}
        value = trip()
        value['days'][1]['daily_start_local'] = '18:00'
        result = self.generate(value, [item, poi(2)], [2])
        self.assertEqual(self.ids(result), ['sh_poi_00002', 'sh_poi_00001'])
        self.assertIn('晚间', ' '.join(result['days'][0]['stops'][1]['reasons']))

    def test_noon_opening_cannot_be_first_stop_at_morning_start(self):
        item = poi(1)
        item['operating_rules']['opening_hours'] = [{'open': '12:00', 'close': '18:00'}]
        result = self.generate(trip(), [item], [2])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(result['skipped_days'][0]['day_index'], 2)

    def test_evening_candidate_is_reconsidered_after_earlier_stops(self):
        value = trip()
        value['days'][1]['daily_start_local'] = '18:00'
        evening = poi(1)
        evening['operating_rules']['opening_hours'] = [{'open': '19:00', 'close': '22:00'}]
        result = self.generate(value, [evening, poi(2)], [2])
        self.assertEqual(self.ids(result), ['sh_poi_00002', 'sh_poi_00001'])

    def test_overnight_last_entry_is_on_following_calendar_day(self):
        value = trip()
        value['days'][1]['daily_start_local'] = '20:00'
        item = poi(1)
        item['operating_rules']['opening_hours'] = [{'open': '20:00', 'close': '02:00', 'close_next_day': True}]
        item['operating_rules']['last_entry_time'] = '01:00'
        result = self.generate(value, [item], [2])
        self.assertEqual(self.ids(result), ['sh_poi_00001'])

    def test_previous_night_window_is_conservatively_not_inferred(self):
        value = trip()
        value['days'][1]['daily_start_local'] = '00:00'
        item = poi(1)
        item['operating_rules']['opening_hours'] = [{'open': '20:00', 'close': '02:00', 'close_next_day': True}]
        self.assertEqual(self.ids(self.generate(value, [item], [2])), [])

    def test_holiday_open_exception_uses_typical_hours_with_warning(self):
        item = poi(1)
        operating = item['operating_rules']
        operating['opening_hours'][0]['weekdays'] = [2, 3, 4, 5, 6, 7]
        operating['closure_rules'] = [{'kind': 'weekly', 'weekday': 1},
                                      {'kind': 'holiday_exception_open', 'date': '2026-10-05'}]
        result = self.generate(trip(), [item], [2])
        self.assertEqual(self.ids(result), ['sh_poi_00001'])
        self.assertIn('核验', ' '.join(result['days'][0]['stops'][0]['warnings']))

    def test_shared_closure_rule_matches_rules_exports(self):
        try:
            shared = importlib.import_module('core.poi_availability')
        except ModuleNotFoundError:
            self.fail('shared availability implementation is missing')
        from modules.rules_engine import rules
        self.assertIs(shared.closure_hit, rules.closure_hit)
        self.assertIs(shared.closure_rule_covers, rules.closure_rule_covers)


if __name__ == '__main__':
    unittest.main()
