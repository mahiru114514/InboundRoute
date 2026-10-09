import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from modules.offline_kit.package import OfflinePackager
from modules.route_adapter.place_names import place_name_en

ROOT = Path(__file__).resolve().parents[1]

class DynamicPlaceTests(unittest.TestCase):
    def resolver(self, **kwargs):
        self.assertIsNotNone(importlib.util.find_spec('modules.route_adapter.place_resolver'), 'Dynamic resolver must exist')
        from modules.route_adapter.place_resolver import PlaceNameResolver
        return PlaceNameResolver(**kwargs)

    def test_screenshot_stations_and_line_terminals_are_known(self):
        for zh, en in [('昌邑路','Changyi Road'),('迎春路','Yingchun Road'),('封浜','Fengbang'),('桂桥路','Guiqiao Road'),('康文路','Kangwen Road'),('航头','Hangtou')]:
            self.assertEqual(place_name_en(zh), en, zh)
        self.assertIn('South Huangpi Road', place_name_en('一大会址·黄陂南路') or '')

    def test_unknown_name_gets_explicit_pinyin_candidate(self):
        r=self.resolver().resolve({'type':'hotel','name_zh':'测试旅馆'})
        self.assertTrue(r['name_en'])
        self.assertEqual(r['status'], 'candidate')
        self.assertEqual(r['source_name_zh'], '测试旅馆')
        self.assertFalse(any('\u4e00'<=c<='\u9fff' for c in r['name_en']))

    def test_unsupported_cjk_character_is_missing_instead_of_fake_english(self):
        self.assertEqual(self.resolver().resolve({'name_zh':chr(0x323AF)})['status'],'missing')

    def test_integer_coordinates_match_browser_json_identity(self):
        from modules.route_adapter.place_resolver import PlaceNameResolver, place_key
        point={'type':'hotel','name_zh':'测试旅馆','coordinate':{'lat':31,'lng':121}}
        resolver=PlaceNameResolver({place_key(point):{'name_en':'Test Inn'}})
        floats={**point,'coordinate':{'lat':31.0,'lng':121.0}}
        self.assertEqual(resolver.resolve(floats)['status'],'confirmed')

    def test_stale_bound_english_is_discarded_after_rename(self):
        r=self.resolver().resolve({'name_zh':'测试旅馆','name_en':'Old Hotel','name_en_for_zh':'旧旅馆'})
        self.assertNotEqual(r['name_en'],'Old Hotel')

    def test_confirmation_is_scoped_and_persisted(self):
        self.assertIsNotNone(importlib.util.find_spec('modules.offline_kit.place_translations'))
        from modules.offline_kit.place_translations import PlaceTranslationStore
        with tempfile.TemporaryDirectory() as tmp:
            s=PlaceTranslationStore(Path(tmp)/'names.json')
            point={'city':'Shanghai','type':'hotel','place_id':'a','name_zh':'测试旅馆'}
            s.confirm(point,'Test Inn')
            restored=PlaceTranslationStore(Path(tmp)/'names.json')
            self.assertEqual(restored.resolve(point)['name_en'],'Test Inn')
            self.assertEqual(restored.resolve(point)['status'],'confirmed')
            self.assertNotEqual(restored.resolve({**point,'place_id':'b'})['name_en'],'Test Inn')
            self.assertNotEqual(restored.resolve({**point,'city':'Suzhou'})['name_en'],'Test Inn')
            self.assertNotEqual(restored.resolve({**point,'name_zh':'新旅馆'})['name_en'],'Test Inn')
            with self.assertRaises(ValueError): s.confirm(point,'测试旅馆')

    def test_new_route_is_translated_without_mutating_trip(self):
        route=json.loads((ROOT/'contracts/examples/route_transit_transfer.json').read_text(encoding='utf-8'))
        ride=next(s for s in route['segments'] if s.get('board'))
        ride['board'].update(station_name_zh='昌邑路',station_name_en=None)
        ride['alight'].update(station_name_zh='迎春路',station_name_en=None)
        ride['line']={'code':'18','name_zh':'地铁18号线(康文路--航头)','name_en':None}
        ride.pop('direction',None)
        trip={'trip_id':'changed','version':8,'days':[{'day_index':1,'date':'2026-10-09','ordered_stops':[{'name_zh':'测试景点','poi_id':'custom','transit_from_previous':route}]}]}
        original=copy.deepcopy(trip)
        payload=OfflinePackager().build(trip)
        self.assertEqual(trip,original)
        stop=payload['days'][0]['stops'][0]
        self.assertEqual(stop['name_zh'],'测试景点')
        stations=stop['stations']
        self.assertTrue(any(s['name_en']=='Changyi Road' for s in stations))
        self.assertTrue(any('Kangwen Road — Hangtou' in l['name_en'] for s in stations for l in s['lines']))
        self.assertEqual(payload['translation_report']['status'],'needs_review')
        self.assertTrue(payload['translation_report']['items'])
        self.assertTrue(payload['translation_version'])

    def test_confirmation_updates_card_and_removes_duplicate_issue(self):
        from modules.route_adapter.place_resolver import PlaceNameResolver, place_key
        point={'type':'poi','poi_id':'custom','name_zh':'测试景点'}
        route={'to':point,'from':{'type':'poi','poi_id':'bund','name_zh':'外滩'},'segments':[]}
        trip={'days':[{'day_index':1,'ordered_stops':[{**point,'stop_type':'poi','transit_from_previous':route}]}]}
        first=OfflinePackager().build(trip)
        issues=[i for i in first['translation_report']['items'] if i['name_zh']=='测试景点']
        self.assertEqual(len(issues),1,'One entity must require only one confirmation')
        resolver=PlaceNameResolver({place_key(point):{'name_en':'Test Attraction'}})
        final=OfflinePackager().build(trip,resolver=resolver)
        self.assertEqual(final['translation_report']['status'],'complete')
        stop=final['days'][0]['stops'][0]
        self.assertEqual(stop['name_en'],'Test Attraction')
        ask=next(c for c in stop['ask_cards'] if c['template_key']=='poi_arrival')
        self.assertEqual(ask['args']['poi_name_en'],'Test Attraction')

    def test_same_name_in_another_city_is_not_shanghai_verified_name(self):
        self.assertEqual(self.resolver().resolve({'city':'Suzhou','name_zh':'世纪公园'})['status'],'candidate')

class TranslationHttpTests(unittest.TestCase):
    def test_old_route_for_replaced_poi_cannot_be_exported(self):
        from modules.offline_kit.service import OfflineKitService
        service=object.__new__(OfflineKitService)
        service.packager=OfflinePackager()
        service._station_provider=lambda _:None
        trip={'version':1,'days':[{'day_index':1,'ordered_stops':[{'poi_id':'new','name_zh':'新天地',
            'arrival_at':0,'departure_at':60,'transit_from_previous':{'duration_seconds':0,'to':{'poi_id':'old','name_zh':'外滩'}}}]}]}
        service._fetch_trip=lambda _:trip
        with self.assertRaisesRegex(ValueError,'交通'):service.generate('test')


    def test_resolve_and_confirmation_api_authentication(self):
        import threading, urllib.request, urllib.error
        from http.server import ThreadingHTTPServer
        from modules.offline_kit.service import OfflineKitService, _make_handler
        with tempfile.TemporaryDirectory() as tmp:
            service=OfflineKitService({},tmp,tmp,None)
            server=ThreadingHTTPServer(('127.0.0.1',0),_make_handler(service))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                def request(path,body,token=None):
                    headers={'Content-Type':'application/json'}
                    if token: headers['X-Module-Token']=token
                    r=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(body).encode(),headers=headers)
                    return json.load(urllib.request.urlopen(r,timeout=3))['data']
                point={'type':'hotel','place_id':'hotel-new','name_zh':'测试旅馆'}
                with self.assertRaises(urllib.error.HTTPError) as denied: request('/place-names',{'points':[point]})
                self.assertEqual(denied.exception.code,403)
                try: first=request('/place-names',{'points':[point]},service.token)
                except urllib.error.HTTPError as exc: self.fail(f'Batch resolution endpoint missing: {exc.code}')
                self.assertEqual(first['entries'][0]['status'],'candidate')
                saved=request('/place-names:confirm',{'point':point,'name_en':'Test Inn'},service.token)
                self.assertNotEqual(first['translation_version'],saved['translation_version'])
                next_batch=request('/place-names',{'points':[point]},service.token)
                self.assertEqual(next_batch['entries'][0]['name_en'],'Test Inn')
                self.assertEqual(next_batch['entries'][0]['status'],'confirmed')
                with self.assertRaises(urllib.error.HTTPError) as invalid: request('/place-names',{'points':[{'name_zh':[]} ]},service.token)
                self.assertEqual(invalid.exception.code,400)
            finally: server.shutdown();server.server_close()

if __name__=='__main__': unittest.main()
