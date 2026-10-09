const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const records = new Map();
const db = {
  close() {}, objectStoreNames: {contains: () => true},
  transaction() {
    const tx = {objectStore: () => ({
      put(record) { records.set(record.trip_id, structuredClone(record)); },
      get(id) { const req = {}; setTimeout(() => {req.result = records.get(id); req.onsuccess?.();}, 0); return req; }
    })};
    setTimeout(() => tx.oncomplete?.(), 5);
    return tx;
  }
};
const ctx = {TextEncoder, Blob, navigator: {}, indexedDB: {open() {
  const req = {result: db}; setTimeout(() => req.onsuccess(), 0); return req;
}}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('modules/offline_kit/web/offline_cache.js', 'utf8'), ctx);
(async () => {
  const cache = ctx.InboundRouteOfflineCache;
  assert.equal((await cache.load('absent', 1)).found, false);
  await cache.save({trip_id:'trip_a', package_version:'0.2.0', ttl_hours:24, trip_version:2, generated_at:Math.floor(Date.now()/1000), payload:{days:[1]}});
  const loaded = await cache.load('trip_a', 2);
  assert.equal(loaded.found, true);
  assert.equal(loaded.stale, false);
  assert.equal(loaded.offline_data.days[0], 1);
  assert.equal(loaded.package_version, '0.2.0');
  assert.equal(loaded.ttl_hours, 24);
  assert.equal((await cache.load('trip_a', 3)).reason, 'version_mismatch');
  await cache.save({trip_id:'trip_old', trip_version:1, generated_at:Math.floor(Date.now()/1000)-90000, payload:{}});
  assert.equal((await cache.load('trip_old', 1)).reason, 'ttl_expired');
  await cache.save({trip_id:'epoch',trip_version:1,generated_at:0,payload:{}});
  const epoch = await cache.load('epoch',1);
  assert.equal(epoch.generated_at,0);
  assert.equal(epoch.stale,true);
  assert.equal(epoch.ttl_hours,24,'legacy packages keep the default TTL');
  await assert.rejects(() => cache.save({trip_id:'large', trip_version:1, payload:'x'.repeat(6*1024*1024)}));
  await cache.save({trip_id:'translated',trip_version:2,package_version:'0.3.0',payload:{translation_version:'names-1',days:[]}});
  assert.equal((await cache.load('translated',2,'names-1')).stale,false);
  assert.equal((await cache.load('translated',2,'names-2')).reason,'translation_mismatch');
  assert.equal((await cache.load('trip_a',2,'names-2')).reason,'translation_mismatch');
  console.log('offline cache: missing record, payload, version, TTL, capacity passed');
})().catch(err => {console.error(err); process.exitCode = 1;});
