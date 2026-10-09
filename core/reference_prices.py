"""已调研的基础参考价。仅供预算估算；不代表指定日期的可订价格。"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'modules/trip_engine/data'
# 明确启用带适用范围的估算记录；未知和实体冲突不启用。
REFERENCE_STATUSES = {'ota_reference', 'official_reference', 'official_republication',
                      'secondary_reference', 'mixed_reference', 'media_reference', 'product_policy_base'}

@lru_cache(maxsize=1)
def _catalog():
    snapshot = json.loads((DATA / 'price_research_2026-10-06.json').read_text(encoding='utf-8'))
    anchors = json.loads((DATA / 'anchors.json').read_text(encoding='utf-8'))
    return {r['entity_id']:r for r in snapshot['hotels'] + snapshot['attractions']}, anchors['hotels']

def _reference(entity_id, day):
    record = _catalog()[0].get(entity_id)
    if not record:
        return None
    low, high = record.get('min_cents'), record.get('max_cents')
    if (not record.get('auto_fill_eligible') or record.get('status') not in REFERENCE_STATUSES or record.get('currency') != 'CNY'
            or type(low) is not int or type(high) is not int or not 0 <= low <= high):
        return None
    if entity_id == 'sh_poi_00107':
        # 日场成人季节价格，不能把30—40作为当天随机价格范围。
        month = int(day[5:7])
        low = high = 4000 if month in (4,5,6,9,10,11) else 3000
    return {'min_cents':low, 'max_cents':high, 'entity_id':entity_id,
            'sources':deepcopy(record['sources']), 'researched_at':record['retrieved_at'],
            'reference_note':record['scope'], 'evidence':record['status']}

def ticket_reference(poi_id, day):
    return _reference(poi_id, day)

def ticket_notices(poi_id, day):
    record = _catalog()[0].get(poi_id) or {}
    notices = []
    for exhibition in record.get('special_exhibitions', []):
        if exhibition['valid_from'] <= day <= exhibition['valid_until']:
            notices.append({'message': '基础费用按免费计入；' + exhibition['conditions'],
                            'sources':deepcopy(exhibition['sources'])})
    return notices

def hotel_reference(endpoint, day):
    if not endpoint or endpoint.get('type') != 'hotel':
        return None
    coordinate = endpoint.get('coordinate') or {}
    if coordinate.get('crs') != 'WGS84':
        return None
    matches = [h for h in _catalog()[1] if h['name_zh'] == endpoint.get('name_zh')
        and all(type(coordinate.get(k)) in (int,float) and abs(coordinate[k] - h[k]) <= .003
                for k in ('lat','lng'))]
    return _reference(matches[0]['id'], day) if len(matches) == 1 else None
