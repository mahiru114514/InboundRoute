"""Inventory missing operational data; never silently marks records verified."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.trip_engine.poi_seed import POIS

if __name__ == '__main__':
    print(json.dumps({
        'poi_count': len(POIS),
        'closure_unverified': [{'poi_id':p['poi_id'],'name':p['names']['zh-Hans']} for p in POIS
                               if p['operating_rules']['closure_data_status'] != 'verified'],
        'lighting_needs_official_review': [p['poi_id'] for p in POIS if p['operating_rules'].get('light_up')],
        'official_review_log':'modules/trip_engine/data/operating_reviews.json',
        'new_batch_review_log':'modules/trip_engine/data/shanghai_poi_reviews_v2.json',
        'missing_opening_hours':sum(not p['operating_rules']['opening_hours'] for p in POIS),
        'unknown_reservation_policy':sum('reservation_required' not in p['operating_rules'] for p in POIS),
        'note':'verified 只描述闭馆规则，不证明全部开放/预约/亮灯/落客数据已核实'
    },ensure_ascii=False,indent=2))
