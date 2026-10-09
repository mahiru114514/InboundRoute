/* InboundRoute 离线包端侧缓存（IndexedDB）
 *
 * 职责：
 *  1. 用 IndexedDB 保存离线包（LocalStorage 容量不足 5MB，故收敛为 IndexedDB）；
 *  2. 绑定 trip.version，版本不一致或超 TTL(24h) 提示「离线数据可能过期」；
 *  3. 容量上限 5MB（字体子集 <=1.5MB 计入，本文件不内嵌字体）。
 *
 * 该文件由 offline_kit 提供，可被 web_workbench 直接引入使用。
 */
(function (global) {
  "use strict";

  var DB_NAME = "inboundroute_offline";
  var STORE = "offline_packages";
  var TTL_HOURS = 24;
  var CAPACITY_MB = 5;

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          var store = db.createObjectStore(STORE, { keyPath: "trip_id" });
          store.createIndex("trip_version", "trip_version", { unique: false });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function tx(db, mode, fn) {
    return new Promise(function (resolve, reject) {
      var t = db.transaction(STORE, mode);
      var store = t.objectStore(STORE);
      var result;
      try { result = fn(store); } catch (err) { reject(err); return; }
      t.oncomplete = function () { db.close(); resolve(result && 'result' in result ? result.result : undefined); };
      t.onerror = t.onabort = function () { db.close(); reject(t.error || new Error('离线缓存写入失败')); };
    });
  }

  function isStale(pkg, now, translationVersion) {
    now = now || Date.now();
    if (pkg.trip_version !== pkg.server_trip_version) {
      return { stale: true, reason: "version_mismatch" };
    }
    if (translationVersion && (pkg.package_version !== '0.3.0' || pkg.payload?.translation_version !== translationVersion)) {
      return { stale: true, reason: 'translation_mismatch' };
    }
    var ageHours = (now - pkg.generated_at_ms) / 3600000;
    if (ageHours > TTL_HOURS) {
      return { stale: true, reason: "ttl_expired" };
    }
    return { stale: false, reason: null };
  }

  async function save(pkg) {
    if (!pkg.trip_id || !Number.isInteger(pkg.trip_version)) throw new Error('离线包缺少行程 ID 或版本');
    if (new TextEncoder().encode(JSON.stringify(pkg)).byteLength > CAPACITY_MB * 1024 * 1024) {
      throw new Error('离线包超过 5MB 上限');
    }
    var db = await openDb();
    var record = {
      trip_id: pkg.trip_id,
      trip_version: pkg.trip_version,
      generated_at_ms: Number.isFinite(pkg.generated_at) ? pkg.generated_at * 1000 : Date.now(),
      package_version: pkg.package_version,
      ttl_hours: TTL_HOURS,
      payload: pkg.payload
    };
    return tx(db, "readwrite", function (store) { store.put(record); });
  }

  async function load(tripId, serverTripVersion, translationVersion) {
    var db = await openDb();
    var record = await tx(db, "readonly", function (store) { return store.get(tripId); });
    if (!record) { return { found: false }; }
    record.server_trip_version = serverTripVersion;
    var stale = isStale(record, Date.now(), translationVersion);
    return {
      found: true,
      stale: stale.stale,
      reason: stale.reason,
      generated_at: record.generated_at_ms / 1000,
      trip_version: record.trip_version,
      package_version: record.package_version,
      ttl_hours: record.ttl_hours || TTL_HOURS,
      offline_data: record.payload
    };
  }

  async function assertCapacity() {
    if (navigator.storage && navigator.storage.estimate) {
      var estimate = await navigator.storage.estimate();
      var usedMb = (estimate.usage || 0) / (1024 * 1024);
      return { ok: usedMb < CAPACITY_MB, used_mb: usedMb };
    }
    return { ok: true, used_mb: null };
  }

  global.InboundRouteOfflineCache = {
    save: save,
    load: load,
    assertCapacity: assertCapacity,
    TTL_HOURS: TTL_HOURS,
    CAPACITY_MB: CAPACITY_MB
  };
})(typeof window !== "undefined" ? window : globalThis);
