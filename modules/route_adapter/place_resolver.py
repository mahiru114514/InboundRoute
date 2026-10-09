"""带来源的地名显示解析；候选是拼音显示名，不宣称官方英文。"""
from __future__ import annotations
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .place_names import has_chinese, place_name_en

DATA = Path(__file__).resolve().parent / 'data'

@lru_cache(maxsize=1)
def pinyin_reference():
    try:
        return json.loads((DATA/'pinyin_display.json').read_text(encoding='utf-8'))['chars']
    except (OSError, ValueError, KeyError):
        return {}

@lru_cache(maxsize=1)
def reference_version():
    digest=hashlib.sha256(b'place-display-v1')
    for path in [DATA/'curated_place_names.json', DATA/'metro_display_names.json', DATA/'pinyin_display.json', DATA/'curated_stations.json',
                 DATA.parent.parent/'trip_engine/data/shanghai_pois_v1.json',
                 DATA.parent.parent/'trip_engine/data/anchors.json', DATA.parent.parent/'trip_engine/data/shanghai_pois_v2.json']:
        try: digest.update(path.read_bytes())
        except OSError: digest.update(str(path.name).encode())
    return digest.hexdigest()[:16]

def place_key(point):
    identity=point.get('place_id') or point.get('station_id') or point.get('poi_id') or point.get('id')
    coordinate=point.get('coordinate') or {}
    # 坐标只作为无 ID 地点的身份信息；不从译名生成坐标。
    def number(value):
        if isinstance(value,float) and value.is_integer(): return int(value)
        return value
    identity=identity or [number(coordinate.get('lat')),number(coordinate.get('lng'))]
    return json.dumps([point.get('city') or 'Shanghai', point.get('type') or 'place', identity,
                       str(point.get('name_zh') or '').strip(), 'en'],ensure_ascii=False,separators=(',',':'),sort_keys=True)

def pinyin_display(name):
    chars=pinyin_reference()
    endings={'大道':'Avenue','公园':'Park','酒店':'Hotel','旅馆':'Inn','机场':'Airport','火车站':'Railway Station','路':'Road','街':'Street'}
    suffix=''
    for zh,en in endings.items():
        if name.endswith(zh) and len(name)>len(zh):
            name,suffix=name[:-len(zh)],en
            break
    result=[]
    for char in name:
        if has_chinese(char):
            if char not in chars: return None
            result.append(chars[char].capitalize())
        elif char.isascii() or char in '·（）':
            result.append({'（':'(', '）':')', '·':'·'}.get(char,char))
        else:
            result.append(char)
    text=' '.join(result).strip()
    return (text+' '+suffix).strip() or None

class PlaceNameResolver:
    def __init__(self, overrides=None):
        self.overrides=dict(overrides or {})
        self.cache={}
        self.version=hashlib.sha256((reference_version()+json.dumps(self.overrides,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()[:16]

    def resolve(self, point):
        if isinstance(point,str): point={'name_zh':point}
        point=point or {}
        name=str(point.get('name_zh') or '').strip()
        key=place_key(point)
        stored=point.get('name_en')
        bound=point.get('name_en_for_zh') or point.get('source_name_zh')
        if bound and bound!=name: stored=None
        cache_key=(key,stored,bound)
        if cache_key in self.cache: return dict(self.cache[cache_key])
        confirmed=self.overrides.get(key)
        if confirmed:
            english,status,source=confirmed['name_en'],'confirmed','user_confirmed'
        elif stored and isinstance(stored,str) and not has_chinese(stored) and stored.strip():
            english,status,source=stored.strip(),'provided','saved_name'
        else:
            known=place_name_en(name) if point.get('city') in (None,'','Shanghai','上海','上海市') else None
            english,status,source=(known,'verified','local_reference') if known else (pinyin_display(name),'candidate','pinyin_display')
            if not english: status,source='missing','unavailable'
        result={'name_zh':name,'name_en':english,'source_name_zh':name,'status':status,'source':source,'key':key}
        self.cache[cache_key]=result
        return dict(result)
