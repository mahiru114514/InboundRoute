"""真实临时 HTTP 服务贯通工作台、行程、规则、路线和离线包。"""
import threading
import unittest
from urllib.parse import quote

import test_web_workbench as wb
from modules.rules_engine.engine import RulesService, build_server
from modules.rules_engine.client import TripEngineClient
from modules.route_adapter.service import RouteAdapterService
from modules.offline_kit.service import OfflineKitService
from contracts.runtime import registry


class FlowTests(unittest.TestCase):
    def test_cost_assessment_and_tail_save_through_workbench(self):
        self.start_engines()
        trip = self.trip()
        path = f"/api/trips/{trip['trip_id']}"
        _, computed, _, _ = self.call('POST', path + '/days/1/routes:compute', {})
        route = computed['data']['routes'][0]
        status, saved, _, _ = self.call('PATCH', path, {'days':[{'day_index':1,'end_transit':route}]})
        self.assertEqual(status, 200, saved)
        costs = {'travelers':2,'taxi_vehicles':1,'intercity_cents':10000,'extras_cents':0,
                 'meal_daily_cents':5000,'lodging_nights':[{'date':'2026-10-12','hotel_name':'酒店',
                 'rooms':1,'room_price_cents':40000}]}
        status, saved, _, _ = self.call('PATCH', path, {'cost_inputs':costs,
            'budget':{'scope':'per_person','currency':'CNY','amount_cents':100000}})
        self.assertEqual(status, 200, saved)
        _, loaded, _, _ = self.call('GET', path)
        data = loaded['data']
        self.assertEqual(data['days'][0]['end_transit'], route)
        self.assertEqual(data['cost_inputs']['intercity_cents'],10000)
        self.assertEqual(data['budget_assessment']['categories']['lodging']['min_cents'],20000)
        self.assertEqual(data['budget_assessment']['status'],'incomplete')
        self.assertTrue(any('演示' in row['message'] for row in data['budget_assessment']['missing']))
        from contracts.generated.schema_store import validate
        # Runtime still uses the existing legacy anchor `at` alias.
        from copy import deepcopy
        canonical = deepcopy(data)
        canonical['anchor_arrival']['arrival_at'] = canonical['anchor_arrival'].pop('at')
        self.assertEqual(validate(canonical,'trip.schema.json'),[])
        status, invalid, _, _ = self.call('PATCH', path, {'cost_inputs':{'travelers':0}})
        self.assertEqual(status,400,invalid)

    def test_budget_update_load_and_clear_through_workbench(self):
        trip = self.trip()
        path = f"/api/trips/{trip['trip_id']}"
        budget = {'scope': 'per_person', 'currency': 'CNY', 'amount_cents': 300050}
        status, result, _, _ = self.call('PATCH', path, {'budget': budget})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['data']['budget'], budget)
        _, result, _, _ = self.call('GET', path)
        self.assertEqual(result['data']['budget'], budget)
        status, result, _, _ = self.call('PATCH', path, {'budget': {**budget, 'amount_cents': -1}})
        self.assertEqual(status, 400, result)
        _, result, _, _ = self.call('PATCH', path, {'budget': None})
        self.assertIsNone(result['data']['budget'])

    def test_airport_hotel_sleep_mixed_timeline_and_offline(self):
        self.start_engines()
        trip = self.trip()
        path = f"/api/trips/{trip['trip_id']}"
        for payload in ({'stop_type': 'arrival_anchor'}, {'stop_type': 'hotel', 'planned_dwell_minutes': 480}):
            status, result, _, _ = self.call('POST', path + '/days/1/stops', payload)
            self.assertEqual(status, 200, result)
        status, routes, _, _ = self.call('POST', path + '/days/1/routes:compute', {})
        self.assertEqual(status, 200, routes)
        self.assertEqual(len(routes['data']['routes']), 3)
        from contracts.generated.schema_store import validate
        for route in routes['data']['routes']:
            self.assertEqual(validate(route, 'route.schema.json'), [])
        self.assertEqual(routes['data']['routes'][0]['duration_seconds'], 0)
        self.assertEqual(routes['data']['routes'][-1]['duration_seconds'], 0)
        for index, route in enumerate(routes['data']['routes'][:2]):
            status, result, _, _ = self.call('PATCH', path, {'days': [{'day_index': 1, 'ordered_stops': [
                {'stop_order': index+1, 'transit_from_previous': route}]}]})
            self.assertEqual(status, 200, result)
        _, evaluated, _, _ = self.call('POST', path + '/rules:evaluate', {'persist': True})
        stops = evaluated['data']['trip']['days'][0]['ordered_stops']
        self.assertEqual(stops[0]['arrival_at'], trip['anchor_arrival']['at'])
        self.assertEqual(stops[1]['departure_at']-stops[1]['arrival_at'], 480*60)
        self.save_final_transfers(path)
        status, result, _, _ = self.call('POST', path + '/offline-package', {})
        self.assertEqual(status, 200, result)
        saved = result['data']['payload']['days'][0]['stops']
        self.assertEqual([s['stop_id'] for s in saved], [s['stop_id'] for s in stops])

    setUp = wb.WorkbenchTests.setUp
    write_registry = wb.WorkbenchTests.write_registry
    call = wb.WorkbenchTests.call

    def tearDown(self):
        for service in reversed(getattr(self, 'extra_services', [])):
            service.stop()
        for server in getattr(self, 'extra_servers', []):
            server.shutdown()
            server.server_close()
        wb.WorkbenchTests.tearDown(self)

    def trip(self):
        return self.trip_service.create_trip({
            'duration_days': 2, 'start_date': '2026-10-12', 'daily_start_local': '09:00',
            'user_profile': {'party_composition': 'solo', 'pacing': 'balanced', 'interests': []},
            'anchor_arrival': {'at': 1791766800, 'location_name': '机场',
                               'coordinate': {'lat': 31.14, 'lng': 121.8, 'crs': 'WGS84'}},
            'anchor_hotel': {'name_zh': '酒店', 'name_en': 'Hotel',
                             'coordinate': {'lat': 31.23, 'lng': 121.47, 'crs': 'WGS84'}}})

    def start_engines(self):
        client = TripEngineClient(f'http://127.0.0.1:{self.trip_server.server_port}', wb.TRIP_TOKEN)
        server = build_server(RulesService(wb.ROOT, client), 'rules-test')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.extra_servers = [server]
        self.write_registry('rules_engine', server.server_port, 'rules-test')
        self.extra_services = []
        route = RouteAdapterService({'provider': 'mock'}, self.root / 'route', self.root,
                                    lambda _: None, wb.ROOT / 'modules' / 'route_adapter')
        route.start()
        self.extra_services.append(route)
        offline = OfflineKitService({}, self.root / 'offline', self.root, lambda _: None)
        offline.start()
        self.extra_services.append(offline)

    def save_final_transfers(self, path):
        _, result, _, _ = self.call('GET', path)
        for day in result['data']['days']:
            status, routes, _, _ = self.call('POST', path + f"/days/{day['day_index']}/routes:compute",
                {'segment_index':len(day['ordered_stops'])})
            self.assertEqual(status,200,routes)
            if routes['data']['routes']:
                status, saved, _, _ = self.call('PATCH',path,{'days':[{'day_index':day['day_index'],
                    'end_transit':routes['data']['routes'][0]}]})
                self.assertEqual(status,200,saved)

    def test_history_lock_reorder_and_invalidate(self):
        trip_id = self.trip()['trip_id']
        path = f'/api/trips/{trip_id}'
        for poi in ('sh_poi_00042', 'sh_poi_00088'):
            self.call('POST', path + '/days/2/stops', {'poi_id': poi})
        status, data, _, _ = self.call('PUT', path + '/days/2/stops',
                                       {'stop_order': ['sh_poi_00088', 'sh_poi_00042']})
        self.assertEqual(status, 200, data)
        status, data, _, _ = self.call('PATCH', path, {'days': [{'day_index': 2,
            'ordered_stops': [{'stop_order': 1, 'locked': True}]}]})
        self.assertEqual(status, 200, data)
        self.assertTrue(data['data']['days'][1]['ordered_stops'][0]['locked'])
        _, history, _, _ = self.call('GET', '/api/trips')
        self.assertIn(trip_id, history['data']['trip_ids'])
        self.assertIn('trips', history['data'])
        self.assertEqual(history['data']['trips'][0]['trip_id'], trip_id)

    def test_rules_routes_and_offline_through_workbench(self):
        self.start_engines()
        trip_id = self.trip()['trip_id']
        path = f'/api/trips/{trip_id}'
        self.call('POST', path + '/days/1/stops', {'poi_id': 'sh_poi_00088'})
        status, evaluated, _, _ = self.call('POST', path + '/rules:evaluate',
                                           {'day_index': 1, 'persist': True})
        self.assertEqual(status, 200, evaluated)
        notice = next(n for n in evaluated['data']['notices'] if n['severity'] == 'hard')
        self.assertIsNone(evaluated['data']['timeline'][0]['stops'][0]['arrival_at'])
        notice_id = notice['message_args']['notice_id']
        status, confirmed, _, _ = self.call('POST', path + f'/conflicts/{quote(notice_id, safe="")}/confirm',
                                           {'decision': 'proceed_anyway'})
        self.assertEqual(status, 200, confirmed)
        status, evaluated, _, _ = self.call('POST', path + '/rules:evaluate', {'persist': True})
        self.assertEqual(status, 200, evaluated)
        self.assertEqual(evaluated['data']['notices'][0]['outcome'], 'confirmed_proceed')
        status, routes, _, _ = self.call('POST', path + '/days/1/routes:compute', {'segment_index': 0})
        self.assertEqual(status, 200, routes)
        route = routes['data']['routes'][0]
        self.assertEqual(route['from']['type'], 'arrival_anchor')
        self.assertEqual(route['to']['name_zh'], '上海博物馆')
        self.assertEqual(len(route['variants']), 3)
        self.call('PATCH', path, {'days': [{'day_index': 1, 'ordered_stops': [
            {'stop_order': 1, 'transit_from_previous': route}]}]})
        _, evaluated, _, _ = self.call('POST', path + '/rules:evaluate', {'persist': True})
        self.assertIsInstance(evaluated['data']['trip']['days'][0]['ordered_stops'][0]['arrival_at'], int)
        self.save_final_transfers(path)
        status, package, _, _ = self.call('POST', path + '/offline-package', {})
        self.assertEqual(status, 200, package)
        offline_stop = package['data']['payload']['days'][0]['stops'][0]
        self.assertTrue(offline_stop['ask_cards'])
        self.assertEqual(offline_stop.get('data_source'), 'mock')
        self.assertEqual(offline_stop.get('name_zh'), '上海博物馆')
        final_transfer=package['data']['payload']['days'][0]['end_transfer']
        self.assertEqual(final_transfer['name_zh'],'酒店')
        self.assertIsInstance(final_transfer['duration_seconds'],int)
        # Changing order invalidates persisted transport as well as clock times.
        self.call('POST', path + '/days/1/stops', {'poi_id': 'sh_poi_00042'})
        _, trip, _, _ = self.call('GET', path)
        self.assertIsNone(trip['data']['days'][0]['ordered_stops'][0]['transit_from_previous'])

    def test_daily_hotel_change_routes_and_offline_through_workbench(self):
        self.start_engines()
        trip = self.trip()
        path = f"/api/trips/{trip['trip_id']}"
        hotel_b = {**trip['anchor_hotel'], 'type': 'hotel', 'name_zh': '酒店B', 'name_en': 'Hotel B',
                   'coordinate': {'lat': 31.24, 'lng': 121.48, 'crs': 'WGS84'}}
        hotel_c = {**hotel_b, 'name_zh': '酒店C', 'name_en': 'Hotel C',
                   'coordinate': {'lat': 31.25, 'lng': 121.49, 'crs': 'WGS84'}}
        status, saved, _, _ = self.call('PATCH', path, {'days': [
            {'day_index': 1, 'end_anchor': hotel_b}, {'day_index': 2, 'end_anchor': hotel_c}]})
        self.assertEqual(status, 200, saved)
        status, routes, _, _ = self.call('POST', path + '/days/2/routes:compute', {'segment_index': 0})
        self.assertEqual(status, 200, routes)
        route = routes['data']['routes'][0]
        self.assertEqual((route['from']['name_zh'], route['to']['name_zh']), ('酒店B', '酒店C'))
        status, rejected, _, _ = self.call('POST', path + '/offline-package', {})
        self.assertEqual(status,400,rejected)
        self.assertIn('终点',rejected['error']['message'])
        self.save_final_transfers(path)
        status, package, _, _ = self.call('POST', path + '/offline-package', {})
        self.assertEqual(status, 200, package)
        day = package['data']['payload']['days'][1]
        self.assertEqual(day['start_anchor']['name_zh'], '酒店B')
        self.assertEqual(day['end_anchor']['name_zh'], '酒店C')
        self.assertEqual(day['end_transfer']['to']['name_zh'],'酒店C')

    def test_missing_rules_returns_explicit_unavailable(self):
        status, body, _, _ = self.call('POST', '/api/trips/test/rules:evaluate', {})
        self.assertEqual(status, 503, body)
        self.assertEqual(body['error']['code'], 'UPSTREAM_DOWN')

    def test_clean_route_restart_reuses_port(self):
        self.start_engines()
        route = self.extra_services[0]
        port = route.port
        route.stop()
        self.assertIsNone(registry.try_read(self.root, 'route_adapter'))
        self.assertEqual(registry.resolve_port({}, 'route_adapter', self.root), port)
        replacement = RouteAdapterService({'provider': 'mock'}, self.root / 'route', self.root,
                                           lambda _: None, wb.ROOT / 'modules' / 'route_adapter')
        self.extra_services[0] = replacement
        replacement.start()
        self.assertEqual(replacement.port, port)

    def test_all_health_contract_versions_match_registration(self):
        self.start_engines()
        import json
        import urllib.request
        for module in ('trip_engine', 'rules_engine', 'route_adapter', 'offline_kit'):
            registration = registry.read(self.root, module)
            with urllib.request.urlopen(registration.base_url + '/health', timeout=5) as response:
                health = json.load(response)
                health = health.get('data', health)
            self.assertEqual(registration.contract_version, registry.CONTRACT_VERSION)
            self.assertEqual(health['contract_version'], registry.CONTRACT_VERSION)


if __name__ == '__main__':
    unittest.main()
