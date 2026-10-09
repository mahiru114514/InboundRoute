"""隔离浏览器验收：真实工作台与离线模块，临时数据，不读写用户行程。"""
import copy,json,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.web_workbench.engine import build_server
from modules.offline_kit.service import OfflineKitService
from modules.trip_engine.poi_seed import POIS
from core.trip_points import enrich_trip_points

ROOT=Path(__file__).resolve().parents[1]
anchors=json.loads((ROOT/'modules/trip_engine/data/anchors.json').read_text(encoding='utf-8'))
base=json.loads((ROOT/'contracts/examples/route_transit_transfer.json').read_text(encoding='utf-8'))
hotel={**next(h for h in anchors['hotels'] if '雅居乐' in h['name_zh']),'type':'hotel'}
hotel['coordinate']={'lat':hotel['lat'],'lng':hotel['lng'],'crs':'WGS84'}
arrival={**anchors['hubs'][0],'type':'arrival_anchor','location_name':anchors['hubs'][0]['name_zh'],'at':int(time.time()),'activity_start_at':int(time.time())}
arrival['coordinate']={'lat':arrival['lat'],'lng':arrival['lng'],'crs':'WGS84'}
def point(p): return {'type':'poi','poi_id':p['poi_id'],'name_zh':p['names']['zh-Hans'],'name_en':p['names']['en'],'coordinate':p['coordinate']}
def route(start,end):
    r=copy.deepcopy(base);r.update(data_source='mock',duration_seconds=3600,mode='transit',**{'from':copy.deepcopy(start),'to':copy.deepcopy(end)})
    ride=next(s for s in r['segments'] if s.get('board'))
    ride['board'].update(station_name_zh='昌邑路',station_name_en=None)
    ride['alight'].update(station_name_zh='迎春路',station_name_en=None)
    ride['line']={'code':'18','name_zh':'地铁18号线(康文路--航头)','name_en':None};ride.pop('direction',None)
    return r
trip={'trip_id':'dynamic_demo','version':1,'status':'draft','timezone':'Asia/Shanghai','start_date':'2026-10-09','duration_days':3,
      'user_profile':{'party_composition':'solo','pacing':'balanced','interests':[],'walking_speed_factor':1,'party_walk_multiplier':1},
      'anchor_hotel':hotel,'anchor_arrival':arrival,'days':[]}
for n,names in enumerate([['新天地','世纪公园','中山公园'],['徐家汇公园','上海自然博物馆','鲁迅公园'],['上海植物园','徐汇滨江绿地']],1):
    day={'day_index':n,'date':f'2026-10-{8+n:02d}','daily_start_local':'09:00','day_status':'fulfilled','poi_cap':4,'ordered_stops':[]}
    start=arrival if n==1 else hotel
    for i,name in enumerate(names,1):
        poi=next(p for p in POIS if p['names']['zh-Hans']==name)
        p=point(poi);r=route(start,p)
        day['ordered_stops'].append({'stop_id':f'stop-{n}-{i}','stop_order':i,'stop_type':'poi','poi_id':p['poi_id'],'name_zh':name,
            'arrival_at':1791507600+(n-1)*86400+i*7200,'departure_at':1791511200+(n-1)*86400+i*7200,'planned_dwell_minutes':60,
            'transit_from_previous':r,'rule_notices':[]})
        start=p
    day['end_transit']=route(start,hotel)
    trip['days'].append(day)
# One unknown place exercises candidate confirmation without any external provider.
p={'type':'hotel','name_zh':'测试旅馆','coordinate':{'lat':31.21,'lng':121.43,'crs':'WGS84'}}
day=trip['days'][2];start=day['end_transit']['from']
day['ordered_stops'].append({**p,'stop_type':'hotel','stop_id':'manual','stop_order':3,'hotel_stay_kind':'rest',
    'planned_dwell_minutes':30,'arrival_at':1791744000,'departure_at':1791745800,'transit_from_previous':route(start,p),'rule_notices':[]})
day['end_transit']=route(p,hotel)
trip=enrich_trip_points(trip)

with tempfile.TemporaryDirectory(prefix='place-browser-') as tmp:
    offline=OfflineKitService({},tmp,tmp,None)
    offline._fetch_trip=lambda _:copy.deepcopy(trip)
    offline._station_provider=lambda _:None
    class Services:
        def snapshot(self):
            modules=['trip_engine','route_adapter','rules_engine','offline_kit']
            return {'services':[{'module_id':m,'ready':True,'health':'ok','purpose':'隔离验收','detail':'演示响应'} for m in modules],
                    'ready':{m:True for m in modules}}
        def call(self,module,method,path,payload=None,headers=None):
            if path=='/pois':return {'pois':POIS}
            if path=='/anchors':return anchors
            if path=='/trips':return {'trips':[{'trip_id':trip['trip_id'],'version':1,'start_date':'2026-10-09','duration_days':3}]}
            if path=='/trips/dynamic_demo':return copy.deepcopy(trip)
            if path.endswith('/rules:evaluate'):return {'trip':copy.deepcopy(trip),'notices':[],'timeline':[],'skipped_rules':[]}
            if path=='/place-names':return offline.resolve_places(payload)
            if path=='/place-names:confirm':return offline.confirm_place(payload)
            if path.endswith('/offline-package'):return offline.generate(trip['trip_id'])
            raise ValueError(path)
    server=build_server(Services(),'isolated-place-token',0,maps={'provider':'none','ready':False})
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print(server.server_port,flush=True)
    sys.stdin.read()
    server.shutdown();server.server_close()
