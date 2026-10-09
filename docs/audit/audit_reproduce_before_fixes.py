"""Read-only audit probes; all mutable data is created in isolated audit folders."""
import concurrent.futures
import http.client
import json
import sys
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'modules/trip_engine'), str(ROOT)]
from test_trip_engine import TripService, build_server, new_trip_payload, TOKEN
from test_external_modules import HealthHandler
from core.manager import Manager
from contracts.runtime import registry
from contracts.generated.schema_store import validate
from modules.rules_engine.engine import RulesService, build_server as rules_server
from modules.rules_engine.client import TripEngineClient
from modules.offline_kit.package import OfflinePackager

DATA = Path(__file__).parent / ('audit-data-' + uuid.uuid4().hex)
DATA.mkdir()
outputs = []

def record(name, data):
    outputs.append({'finding': name, **data})
    print(json.dumps(outputs[-1], ensure_ascii=True))

def call(server, method, path, body=None, version=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    headers = {'X-Module-Token': TOKEN, 'Content-Type': 'application/json'}
    if version is not None:
        headers['If-Match'] = str(version)
    try:
        conn.request(method, path, None if body is None else json.dumps(body), headers)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()

service = TripService(DATA / 'trips')
trip = service.create_trip(new_trip_payload())
errors = [str(error).split('\n')[0] for error in validate(trip, 'trip.schema.json')]
assert errors
record('contract_anchor_fields', {'errors': errors})

server = build_server(service, TOKEN)
threading.Thread(target=server.serve_forever, daemon=True).start()
rules = rules_server(RulesService(ROOT, TripEngineClient(f'http://127.0.0.1:{server.server_port}', TOKEN)), TOKEN)
threading.Thread(target=rules.serve_forever, daemon=True).start()
try:
    service.add_stop(trip['trip_id'], 1, {'poi_id': 'sh_poi_00088'})
    prefix = f"/trips/{trip['trip_id']}/conflicts/"
    notice = 'rule_01_closure:1:sh_poi_00088'
    encoded = call(rules, 'POST', prefix + notice.replace(':', '%3A') + '/confirm', {'decision': 'proceed_anyway'})
    plain = call(rules, 'POST', prefix + notice + '/confirm', {'decision': 'proceed_anyway'})
    assert encoded[0] == 400 and plain[0] == 200
    record('encoded_conflict_confirmation', {'encoded_status': encoded[0], 'encoded_error': encoded[1]['error'], 'plain_status': plain[0]})

    race_trip = service.create_trip(new_trip_payload())
    original_get = service.store.get
    barrier = threading.Barrier(2)
    def simultaneous_get(trip_id):
        result = original_get(trip_id)
        if trip_id == race_trip['trip_id']:
            barrier.wait(timeout=5)
        return result
    service.store.get = simultaneous_get
    try:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(call, server, 'PATCH', f"/trips/{race_trip['trip_id']}", patch, 1)
                       for patch in [{'user_profile': {'pacing': 'packed'}}, {'daily_start_local': '11:00'}]]
            responses = [f.result() for f in futures]
    finally:
        service.store.get = original_get
    final = original_get(race_trip['trip_id'])
    assert [r[0] for r in responses] == [200, 200] and final['version'] == 2
    assert not (final['user_profile']['pacing'] == 'packed' and final['days'][0]['daily_start_local'] == '11:00')
    record('lost_update_with_if_match', {'statuses': [r[0] for r in responses], 'version': final['version'], 'pacing': final['user_profile']['pacing'], 'daily_start': final['days'][0]['daily_start_local']})
finally:
    rules.shutdown(); rules.server_close()
    server.shutdown(); server.server_close()

workspace = DATA / 'manager'
for module_id, deps in [('trip_engine', []), ('rules_engine', ['trip_engine'])]:
    folder = workspace / 'modules' / module_id
    folder.mkdir(parents=True)
    manifest = {'id': module_id, 'name': module_id, 'version': '1', 'dependencies': deps}
    if module_id == 'trip_engine':
        manifest['service'] = {'enabled': True, 'health_path': '/health'}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (folder / 'plugin.py').write_text('def run(ctx):\n    pass\n', encoding='utf-8')
external = __import__('http.server', fromlist=['ThreadingHTTPServer']).ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
threading.Thread(target=external.serve_forever, daemon=True).start()
manager = Manager(workspace)
registry.write(registry.build_registration('trip_engine', external.server_port, TOKEN), workspace)
try:
    manager.enable('trip_engine'); manager.enable('rules_engine')
    card = next(c for c in manager.list() if c['id'] == 'trip_engine')
    try:
        manager.start('rules_engine')
        raise AssertionError('expected dependency rejection')
    except ValueError as exc:
        assert card['status'] == 'running' and card['external']
        record('external_dependency_rejected', {'dependency_status': card['status'], 'external': card['external'], 'error': str(exc)})
finally:
    manager.close(); external.shutdown(); external.server_close()

sticky_workspace = DATA / 'sticky'
sock = registry.bind_socket('127.0.0.1', 0)
port = sock.getsockname()[1]
sock.close()
reg = registry.build_registration('sticky_svc', port, TOKEN)
reg.pid = 4194304
assert not registry.process_alive(reg.pid)
registry.write(reg, sticky_workspace)
before = registry.resolve_port({}, 'sticky_svc', sticky_workspace)
registry.remove(sticky_workspace, 'sticky_svc')
after = registry.resolve_port({}, 'sticky_svc', sticky_workspace)
assert before == port and after == 0
record('port_memory_removed_on_stop', {'before_stop': before, 'after_stop': after})

fake_trip = {'days': [{'day_index': 1, 'date': '2026-10-12', 'ordered_stops': [{
    'stop_order': 1, 'stop_type': 'poi', 'poi_id': 'sh_poi_00042',
    'transit_from_previous': {'data_source': 'mock', 'to': {'name_zh': '外滩', 'name_en': 'The Bund'}, 'segments': []}
}]}]}
stop = OfflinePackager().build(fake_trip)['days'][0]['stops'][0]
assert 'data_source' not in stop and 'name_zh' not in stop
record('offline_source_and_name_lost', {'input_source': 'mock', 'output_keys': sorted(stop), 'mock_warning_condition': stop.get('data_source') == 'mock'})

(DATA / 'results.json').write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding='utf-8')
print('AUDIT_RESULTS=' + str(DATA / 'results.json'))
