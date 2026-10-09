"""推荐接口契约覆盖写入计划、响应与排程日期请求。"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]


class RecommendationContractTests(unittest.TestCase):
    def validator(self, definition=None):
        if Draft202012Validator is None:
            self.skipTest('未安装可选 jsonschema，跳过结构校验')
        path = ROOT / 'contracts/schemas/recommendation.schema.json'
        self.assertTrue(path.exists(), '推荐请求/响应契约尚未登记')
        schema = json.loads(path.read_text(encoding='utf-8'))
        if definition:
            schema = {'$ref':'#/$defs/' + definition,'$defs':schema['$defs']}
        return Draft202012Validator(schema)

    def test_valid_readonly_result(self):
        result = {
            'trip_id':None,'trip_version':None,'warnings':[], 'skipped_days':[],
            'plan':{'days':[{'day_index':2,'stops':[{'poi_id':'sh_poi_00042','planned_dwell_minutes':90}]}]},
            'days':[{'day_index':2,'date':'2026-10-13','stops':[{
                'poi_id':'sh_poi_00042','name_zh':'外滩','planned_dwell_minutes':90,
                'reasons':['匹配兴趣'],'warnings':['交通为估算'],
            }]}],
        }
        errors = list(self.validator().iter_errors(result))
        self.assertEqual(errors, [], str(errors))
        from contracts.generated.models import build
        self.assertEqual(build('recommendation.schema.json', result).to_dict(), result)

    def test_plan_rejects_unknown_fields_and_invalid_dwell(self):
        validator = self.validator('plan')
        good = {'days':[{'day_index':2,'stops':[{'poi_id':'sh_poi_00042','planned_dwell_minutes':90}]}]}
        self.assertTrue(validator.is_valid(good))
        for field,value in [('planned_dwell_minutes',True),('planned_dwell_minutes',721),('locked',True)]:
            bad = deepcopy(good)
            bad['days'][0]['stops'][0][field] = value
            self.assertFalse(validator.is_valid(bad))

    def test_request_requires_exactly_one_source_and_unique_days(self):
        validator = self.validator('generate_request')
        self.assertTrue(validator.is_valid({'trip_id':'trip_abc','day_indices':[2,3]}))
        self.assertFalse(validator.is_valid({'trip_id':'trip_abc','setup':{},'day_indices':[2]}))
        self.assertFalse(validator.is_valid({'trip_id':'trip_abc','day_indices':[2,2]}))
        self.assertFalse(validator.is_valid({'trip_id':'trip_abc','day_indices':[]}))
        self.assertFalse(validator.is_valid({'trip_id':'trip_abc','day_indices':[True]}))

    def test_generated_request_models_keep_full_setup(self):
        from contracts.generated.models import GenerateRequest, CreateRequest
        from tests.test_trip_engine import new_trip_payload
        setup = new_trip_payload(duration_days=5)
        setup.update({'budget':{'scope':'per_person','currency':'CNY','amount_cents':100000},
                      'anchor_departure':{'at':1792195200,'location_name':'浦东机场',
                                          'coordinate':{'lat':31.1443,'lng':121.8083,'crs':'WGS84'}}})
        request = GenerateRequest.from_dict({'setup':setup,'day_indices':[2,3]})
        self.assertEqual(request.to_dict()['setup'], setup)
        plan = {'days':[{'day_index':2,'stops':[{'poi_id':'sh_poi_00042','planned_dwell_minutes':90}]}]}
        self.assertEqual(CreateRequest.from_dict({'setup':setup,'plan':plan}).to_dict()['setup'], setup)


if __name__ == '__main__':
    unittest.main()
