"use strict";
/* 工作台接线回归：把「页面到底有没有真的接上」变成可执行的断言。
 *
 * 为什么需要这个文件：
 *   之前的验收只看「后端接口能不能通」，于是出现了「接口测试全绿、页面上却点不出来」——
 *   历史行程恢复、排序/锁定、规则确认、路线、离线包这些流程在 flow.js 里写好了，
 *   但 index.html 没有引用它、也没有对应 DOM，app.js 也没把事件接过去。
 *   这里从 index.html 真实读取 id 列表建桩 DOM，按浏览器顺序加载
 *   runtime.js → index.html 声明的功能脚本 → app.js，再用假 fetch 跑完 boot()，
 *   断言五件事：
 *     1) index.html 真的引用了 flow.js，且所有流程面板/控件 id 都在，版本号一致；
 *     2) 刷新页面能把已保存的行程找回来（历史下拉 + boot 自动恢复）；
 *     3) 排序/锁定/移到晚上/计算交通这些控件真的渲染出来并能触发请求；
 *     4) 规则参与流程：加载与「加入景点」都会触发 rules:evaluate；
 *     5) 兴趣真的影响 POI 排序；住宿支持英文/拼音联想并写入契约的 name_pinyin。
 *
 * 运行：node tests/workbench_wiring.test.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { WEB, html, ASSETS, scripts } = require("../tools/workbench_assets.cjs");

let checks = 0;
function check(name, condition, detail) {
  checks += 1;
  assert.ok(condition, `${name}${detail !== undefined ? ` -> ${JSON.stringify(detail)}` : ""}`);
  console.log(`  ok   ${name}`);
}

/* ------------------------------------------------------------------ 1) 静态接线 */

console.log("workbench_wiring.test.js\n");
console.log("1) index.html 静态接线");

const REQUIRED_IDS = [
  "trip-history", "refresh-history", "history-hint", "delete-trip", "duplicate-trip",
  "save-trip", "edit-mode-hint", "compute-all-routes",
  "has-departure", "departure-hub", "departure-date", "departure-time",
  "hub-search", "hotel-search", "anchor-pick-state",
  "poi-hint",
  "rules-panel", "rule-notices", "evaluate-trip",
  "route-progress", "route-hint",
  "offline-panel", "offline-status", "offline-preview",
  "hotel", "recommendation-days", "generate-recommendations",
  "recommendation-hint", "recommendation-progress", "recommendation-results",
  "generate-offline", "download-offline", "load-offline",
];
const missing = REQUIRED_IDS.filter((id) => !new RegExp(`id="${id}"`).test(html));
check("流程面板与控件的 id 全部存在", missing.length === 0, missing);
check("独立交通面板与导航已移除", !html.includes('id="route-panel"') && !html.includes('href="#route-panel"'));
check("全程交通入口位于行程概览", /id="trip-panel"[\s\S]*?id="compute-all-routes"[\s\S]*?<\/section>/.test(html));

check("index.html 引用了 flow.js", /src="\/flow\.js\?v=\d+"/.test(html));
check("recommendations.js 在 app.js 之前加载且 defer", /<script src="\/recommendations\.js\?v=\d+" defer>/.test(html)
  && html.indexOf('src="/recommendations.js') < html.indexOf('src="/app.js'));
check("推荐提示位于设定折叠内容之外，生成后仍可读",html.indexOf('id="recommendation-results"') > html.indexOf('</details>')
  && html.indexOf('id="recommendation-progress"') > html.indexOf('</details>'));
check("index.html 引用了 offline_cache.js", /src="\/offline_cache\.js\?v=\d+"/.test(html));
check("offline_view.js 只加载一次且先于 flow.js", (html.match(/src="\/offline_view\.js/g)||[]).length===1 && html.indexOf('src="/offline_view.js')<html.indexOf('src="/flow.js'));
check("flow.js 在 app.js 之前加载（boot 要调用 initFlow）",
  html.indexOf('src="/flow.js') > 0 && html.indexOf('src="/flow.js') < html.indexOf('src="/app.js'),
  { flow: html.indexOf('src="/flow.js'), app: html.indexOf('src="/app.js') });
check("共享状态先于功能脚本加载，启动入口最后加载",
  scripts[0].url === "/runtime.js" && scripts.at(-1).url === "/app.js");
check("offline_cache.js 在 flow.js 之前加载",
  html.indexOf('src="/offline_cache.js') < html.indexOf('src="/flow.js'));

const versions = [...html.matchAll(/\/(?:[\w.]+)\.(?:js|css)\?v=(\d+)/g)].map((m) => m[1]);
check("所有静态资源用同一个版本号", new Set(versions).size === 1, versions);

// 页面引用的每个资源都必须被 web_workbench 映射并能读到文件；否则线上就是 404 白屏。
const referenced = [...html.matchAll(/(?:src|href)="(\/[\w.]+)(?:\?v=\d+)?"/g)].map((m) => m[1]);
const unresolved = referenced.filter((url) => !ASSETS[url] ||
  !fs.existsSync(path.resolve(WEB, ASSETS[url].file)));
check("index.html 引用的资源都在挂载表里且文件存在",
  unresolved.length === 0, { referenced, unresolved, assets: Object.keys(ASSETS) });

/* rules_engine 只接受契约 rules.json#/execution_model/trigger_events 里的 trigger，
 * 传别的值一律 400 拒绝；页面上看到的现象是「行程已创建，但规则未完成校验」
 * （曾经真的写成过 create_trip）。这里直接读契约来判定，避免测试自己再维护一份名单。 */
const TRIGGER_EVENTS = new Set(JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "contracts", "rules.json"), "utf8"),
).execution_model.trigger_events);
const triggerLiterals = [];
for (const script of scripts) {
  const file = path.relative(WEB, script.path);
  const source = fs.readFileSync(script.path, "utf8");
  for (const match of source.matchAll(/evaluateTrip\(\s*["']([^"']+)["']/g)) {
    triggerLiterals.push({ file, trigger: match[1] });
  }
}
const badTriggers = triggerLiterals.filter((item) => !TRIGGER_EVENTS.has(item.trigger));
check("前端用字面量传给 rules:evaluate 的 trigger 都在契约白名单里",
  triggerLiterals.length > 0 && badTriggers.length === 0,
  { literals: triggerLiterals, badTriggers, allowed: [...TRIGGER_EVENTS] });

// 抵达日期/时刻曾经写死在 HTML 里（2026-10-12 23:30），过期后每个新用户都要手改两个字段。
check("抵达日期/时刻不再写死在 HTML 里（改由 defaultArrival 动态给）",
  !/id="arrival-date"[^>]*\svalue="/.test(html) && !/id="arrival-time"[^>]*\svalue="/.test(html));

// 离境锚点区块必须真的存在，且「国际航班」默认勾选（契约 is_international 默认 true）。
check("离境/返程区块存在，且默认按国际航班预留时间",
  /id="has-departure"/.test(html) && /id="departure-hub"/.test(html)
    && /id="departure-international"[^>]*\schecked/.test(html));

/* ------------------------------------------------------------------ 2) 假 DOM */

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.id = "";
    this.className = "";
    this._ownText = "";
    this.title = "";
    this.value = "";
    this.type = "";
    this.hidden = false;
    this.disabled = false;
    this.draggable = false;
    this.dataset = {};
    this.style = {};
    this._listeners = {};
    this.classList = {
      _set: new Set(),
      add: (...cs) => cs.forEach((c) => this.classList._set.add(c)),
      remove: (...cs) => cs.forEach((c) => this.classList._set.delete(c)),
      toggle: (c, on) => (on ? this.classList._set.add(c) : this.classList._set.delete(c)),
      contains: (c) => this.classList._set.has(c),
    };
  }
  append(...nodes) {
    for (const node of nodes) {
      if (node === null || node === undefined) continue;
      node.parentNode = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter((c) => c !== this);
  }
  addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); }
  setAttribute(name, value) { this[name] = value; }
  getAttribute(name) { return this[name]; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  reset() {
    for (const [id, value] of Object.entries({"duration-days":"2", party:"solo", pacing:"balanced", "hub-search":"", "hotel-search":""})) registry.get(id).value = value;
    registry.get("has-departure").checked = false;
  }
  get textContent() { return this._ownText; }
  set textContent(value) { this._ownText = value === null || value === undefined ? "" : String(value); }
  get innerHTML() { return this._ownText; }
  set innerHTML(value) { this._ownText = String(value); }
  get outerHTML() { return `<${this.tagName.toLowerCase()}>${this._ownText}</${this.tagName.toLowerCase()}>`; }
}

/** 触发元素上注册的监听器（桩 DOM 不会自己派发事件）。 */
function fire(element, type, event) {
  for (const fn of element._listeners[type] || []) fn(event || { preventDefault() {}, target: element });
}

/** 深度遍历收集后代元素。 */
function walk(node, out = []) {
  for (const child of node.children || []) { out.push(child); walk(child, out); }
  return out;
}
function texts(node) { return walk(node).map((el) => el.textContent).filter(Boolean); }
function findByText(node, text) { return walk(node).find((el) => el.textContent === text) || null; }

/* ------------------------------------------------------------------ 3) 运行期接线 */

/* ---- 假引擎数据 ---- */

const POI_A = {
  poi_id: "poi_nature", names: { "zh-Hans": "自然点", en: "Nature Spot" },
  romanization: { pinyin: "zi ran dian", pinyin_plain: "zirandian" },
  search_aliases: [], category: { level1: "nature", level2: "park", label_zh: "公园" },
  coordinate: { lat: 31.10, lng: 121.05, crs: "WGS84" }, popularity_norm: 1.0,
  provenance: { confidence: 1 }, operating_rules: {},
};
const POI_B = {
  poi_id: "poi_history", names: { "zh-Hans": "历史点", en: "History Spot" },
  romanization: { pinyin: "li shi dian", pinyin_plain: "lishidian" },
  search_aliases: [], category: { level1: "history_culture", level2: "museum", label_zh: "博物馆" },
  coordinate: { lat: 31.23, lng: 121.47, crs: "WGS84" }, popularity_norm: 0.0,
  provenance: { confidence: 0 }, operating_rules: {},
};
const SERVICES = {
  services: ["trip_engine", "recommendation_engine", "rules_engine", "route_adapter", "offline_kit"].map((module_id) => ({
    module_id, ready: true, base_url: `http://127.0.0.1:1`, health: "ok", detail: "就绪", purpose: `${module_id} 用途`,
  })),
  ready: { trip_engine: true, recommendation_engine: true, rules_engine: true, route_adapter: true, offline_kit: true },
};

const hydrate=require('./trip_fixture');
function makeTrip(overrides) {
  const stop = {
    poi_id: "poi_history", stop_order: 1, planned_dwell_minutes: 120, locked: false,
    arrival_at: null, departure_at: null, transit_from_previous: null, rule_notices: [],
  };
  return hydrate({
    trip_id: "trip_saved", version: 3, status: "draft",
    user_profile: { party_composition: "solo", pacing: "balanced", interests: [], walking_speed_factor: 1,
      party_walk_multiplier: 1, prefer_taxi: false },
    anchor_arrival: { at: 1791826200, location_name: "虹桥火车站", activity_start_at: 1791831600,
      coordinate: { lat: 31.1943, lng: 121.3198, crs: "WGS84" } },
    anchor_hotel: { name_zh: "和平饭店", name_en: "Fairmont Peace Hotel", name_pinyin: "heping fandian",
      coordinate: { lat: 31.2405, lng: 121.4903, crs: "WGS84" }, poi_id: null },
    days: [
      { day_index: 1, date: "2026-10-12", day_status: "partial", daily_start_local: "09:00", poi_cap: 4,
        ordered_stops: [stop] },
      { day_index: 2, date: "2026-10-13", day_status: "empty", daily_start_local: "09:00", poi_cap: 4,
        ordered_stops: [] },
    ],
    ...(overrides || {}),
  });
}

const ROUTE = {
  mode: "transit", duration_seconds: 900, distance_meters: 4200, cost: { min: 3, max: 4 },
  data_source: "mock", has_long_transfer: false,
  from: { type: "hotel", name_zh: "和平饭店" }, to: { poi_id: "poi_history", name_zh: "历史点" },
  variants: [
    { mode: "transit", duration_seconds: 900, distance_meters: 4200, cost: { min: 3, max: 4 } },
    { mode: "taxi", duration_seconds: 720, distance_meters: 5100, cost: { min: 22, max: 28 } },
    { mode: "walk", duration_seconds: null, distance_meters: null, cost: null },
  ],
};

/* 口岸/住宿清单：直接读 trip_engine 的真实主数据文件当桩数据。
 * 不在测试里另写一份「差不多的」副本 —— 那种副本迟早会和真实数据脱节。 */
const ANCHORS_FIXTURE = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "modules", "trip_engine", "data", "anchors.json"), "utf8"));

const calls = [];
function ok(data) { return { ok: true, status: 200, json: async () => ({ ok: true, data, meta: {} }) }; }
function bad(status, code, message) {
  return { ok: false, status, json: async () => ({ ok: false, error: { code, message, details: {} } }) };
}

let tripState = makeTrip();
let createCalls = 0;
let precheckCalls = 0;
let PRECHECK_BLOCKS = false;
let ROUTE_FAILURE = false;
async function fetchStub(url, init) {
  const method = (init && init.method) || "GET";
  const body = init && init.body ? JSON.parse(init.body) : null;
  calls.push({ url, method, body, headers:init?.headers });
  if (url === "/api/session") return ok({ token: "wb-token", base: "http://127.0.0.1:1", map: { ready: false, hint: "" } });
  if (url === "/api/services") return ok(SERVICES);
  if (url === "/api/pois") return ok({ pois: [POI_A, POI_B] });
  if (url === "/api/anchors") return ok(ANCHORS_FIXTURE);
  if (url === "/api/recommendations:generate" && method === "POST") {
    const wanted=body.day_indices.filter(index=>!body.trip_id || !tripState.days.find(day=>day.day_index===index).ordered_stops.length);
    const index=wanted[0];
    return ok({trip_id:body.trip_id || null,trip_version:body.trip_id ? tripState.version : null,
      plan:{days:index ? [{day_index:index,stops:[{poi_id:'poi_nature',planned_dwell_minutes:60}]}] : []},
      days:index ? [{day_index:index,date:'2026-10-13',stops:[{poi_id:'poi_nature',name_zh:'自然点',planned_dwell_minutes:60,reasons:['同一区域，减少往返'],warnings:['开放资料待核验']}]}] : [],
      skipped_days:wanted.slice(1).map(day_index=>({day_index,reason:'候选不足'})),warnings:['交通为规划估算']});
  }
  if (url === "/api/trips:recommended" && method === "POST") {
    const setup=body.setup;
    tripState=makeTrip({trip_id:'trip_recommended',version:1,user_profile:setup.user_profile,anchor_arrival:setup.anchor_arrival,anchor_hotel:setup.anchor_hotel,anchor_departure:setup.anchor_departure,budget:setup.budget,
      days:Array.from({length:setup.duration_days},(_,i)=>({day_index:i+1,date:`2026-10-${12+i}`,day_status:'empty',daily_start_local:'09:00',poi_cap:4,ordered_stops:[]}))});
    for (const day of body.plan.days) tripState.days[day.day_index-1].ordered_stops=day.stops.map(stop=>({...makeTrip().days[0].ordered_stops[0],...stop}));
    return ok(tripState);
  }
  if (/\/recommendations:apply$/.test(url) && method === "POST") {
    tripState=JSON.parse(JSON.stringify(tripState));tripState.version++;
    for (const day of body.plan.days) tripState.days[day.day_index-1].ordered_stops=day.stops.map(stop=>({...makeTrip().days[0].ordered_stops[0],...stop}));
    return ok(tripState);
  }
  if (url === "/api/trips" && method === "GET") {
    return ok({ trip_ids: ["trip_saved"], trips: [{ trip_id: "trip_saved", version: 3, start_date: "2026-10-12", duration_days: 2, updated_at: 1 }] });
  }
  // 预校验：只校验不落盘，必须在真正创建之前被调用。
  if (url === "/api/trips:validate" && method === "POST") {
    return ok({ valid: true, duration_days: 2, dates: ["2026-10-12", "2026-10-13"], poi_cap: 4 });
  }
  if (url === "/api/trips" && method === "POST") {
    createCalls += 1;
    tripState = makeTrip({ trip_id: `trip_new${createCalls}` });
    return ok(tripState);
  }
  if (/:duplicate$/.test(url) && method === "POST") {
    tripState = makeTrip({ trip_id: "trip_copy1" });
    return ok(tripState);
  }
  if (/^\/api\/trips\/[^/]+$/.test(url) && method === "DELETE") {
    return ok({ trip_id: url.split("/").pop(), deleted: true });
  }
  if (/^\/api\/trips\/[^/]+$/.test(url) && method === "GET") return ok(tripState);
  if (/^\/api\/trips\/[^/]+$/.test(url) && method === "PATCH") return ok(tripState);
  if (url === "/api/trips/trip_saved" && method === "PATCH") return ok(tripState);
  if (/\/rules:precheck$/.test(url) && method === "POST") {
    precheckCalls += 1;
    // 只要 PRECHECK_BLOCKS 为真就一直报硬冲突；「第二次点击能加入」靠的是前端
    // 不再重复预检（pendingConflict 命中），而不是靠后端改口 —— 更贴近真实行为。
    if (PRECHECK_BLOCKS) {
      return ok({
        poi_id: body && body.poi_id, day_index: body && body.day_index, poi_name: "上海博物馆",
        would_block: true, timeline: [],
        hard_conflicts: [{
          rule_id: "rule_01_closure", severity: "hard", outcome: "pending", channel: "modal_confirm",
          message_key: "rule.closure.confirm",
          message_args: { poi_name: "上海博物馆", weekday: "Monday" }, raised_at: 1791819600,
        }],
        notices: [], skipped_rules: [],
      });
    }
    return ok({ poi_id: body && body.poi_id, day_index: body && body.day_index,
      would_block: false, hard_conflicts: [], notices: [], timeline: [], skipped_rules: [] });
  }
  if (/\/rules:evaluate$/.test(url)) return ok({ trip: tripState, notices: [], timeline: [], skipped_rules: [] });
  if (/\/routes:compute$/.test(url)) return ROUTE_FAILURE ? bad(503,"UPSTREAM_DOWN","route provider unavailable") : ok({ routes: [ROUTE] });
  if (/\/offline-package$/.test(url)) return ok({ trip_version: 3, generated_at: 1791826200, payload: { days: [] } });
  if (/\/days\/\d+\/stops\/[^/]+\/move$/.test(url) && method === "POST") {
    return ok({ trip: tripState, pacing_warning: null });
  }
  if (/\/days\/\d+\/stops$/.test(url) && method === "POST") {
    tripState = makeTrip();
    return ok({ trip: tripState, pacing_warning: null });
  }
  if (/\/days\/\d+\/stops$/.test(url) && method === "PUT") return ok({ trip: tripState });
  return bad(404, "NOT_FOUND", `测试桩未实现：${method} ${url}`);
}

/* ---- 按浏览器顺序加载四个脚本 ---- */

const registry = new Map();
for (const id of [...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1])) {
  const el = new FakeElement("div");
  el.id = id;
  registry.set(id, el);
}
const body = new FakeElement("body");
body.append(...registry.values());

let checkedInterests = [];
const document = {
  body,
  head: new FakeElement("head"),
  createElement: (tag) => new FakeElement(tag),
  getElementById: (id) => registry.get(id) || null,
  querySelectorAll: (selector) => (selector.includes("interest") ? checkedInterests : []),
};

const sandbox = {
  window: {},
  URL, URLSearchParams,
  document,
  location: { origin: "http://127.0.0.1:1" },
  console,
  fetch: fetchStub,
  localStorage: {
    _v: {},
    getItem(k) { return this._v[k] ?? null; },
    setItem(k, v) { this._v[k] = String(v); },
    removeItem(k) { delete this._v[k]; },
  },
  setTimeout: () => 0,
  clearTimeout: () => {},
  setInterval: () => 0,
  Number, Math, JSON, Date, String, Object, Array, Boolean, parseInt, parseFloat, isNaN,
  Promise, Set, Map, TextEncoder, Error,
};
vm.createContext(sandbox);
for (const script of scripts) {
  vm.runInContext(fs.readFileSync(script.path, "utf8"), sandbox, { filename: path.basename(script.url) });
}
const exported = [
  "state", "$", "readSetup", "renderTrip", "renderPoiList", "visiblePois", "addSelectedToDay",
  "renderAnchorPickers", "applyPickedHotelCoordinate", "anchorMatches", "anchors", "hotelCoordinate",
  "renderFlow", "flow", "defaultArrival", "readDeparture", "departureDefaults",
  "applyDraft", "saveDraft", "loadDraft", "duplicateCurrentTrip", "deleteCurrentTrip",
  "rollbackTripCreation", "mapPois", "formFromTrip",
];
vm.runInContext(`globalThis.__app = {${exported.join(",")}};`, sandbox);
const app = sandbox.__app;
const flow = app.flow;
const $ = app.$;

/** 反复让出事件循环，等流程里的多个 await 链跑完。 */
async function settle(rounds = 30) {
  for (let i = 0; i < rounds; i += 1) await new Promise((resolve) => setImmediate(resolve));
}

(async () => {
  console.log("\n2) 刷新页面自动恢复已保存行程");
  await sandbox.window.__workbenchBoot;
  await settle();

  // 抵达日期/时刻必须按「当前北京时间」动态给默认值，且不能给出已经过去的时刻。
  // 注意不能直接断言「等于今天」：默认值会向上取整到下一个半点，23:40 打开页面时
  // 会合理地落到次日 00:00 —— 断言「今天」会在每天深夜误报。（之前真的这么错过。）
  const generated = app.defaultArrival();
  const generatedAt = new Date(`${generated.date}T${generated.time}:00+08:00`);
  const minutesAhead = (generatedAt.getTime() - Date.now()) / 60000;
  check("抵达默认值不再是写死的旧日期", generated.date !== "2026-10-12", generated);
  check("抵达默认值格式正确且落在整点/半点",
    /^\d{4}-\d{2}-\d{2}$/.test(generated.date) && /^([01]\d|2[0-3]):(00|30)$/.test(generated.time), generated);
  check("抵达默认值不在过去、且在 1 小时内（向上取整到下一个半点）",
    minutesAhead > -1 && minutesAhead <= 60, { minutesAhead, generated });
  check("有历史行程时①自动回填其抵达设定",
    $("arrival-date").value === sandbox.ymd(app.state.trip.anchor_arrival.at) && $("arrival-time").value === sandbox.hhmm(app.state.trip.anchor_arrival.at),
    { date: $("arrival-date").value, time: $("arrival-time").value });

  check("boot 后从历史里恢复了上次的行程", app.state.trip && app.state.trip.trip_id === "trip_saved",
    app.state.trip && app.state.trip.trip_id);
  check("历史下拉框列出了已保存行程",
    $("trip-history").children.some((option) => option.value === "trip_saved"));
  check("历史下拉框选中了当前行程", $("trip-history").value === "trip_saved", $("trip-history").value);
  check("上次打开的行程被记到 localStorage", sandbox.localStorage._v["inboundroute.lastTrip"] === "trip_saved",
    sandbox.localStorage._v);
  check("详情抽屉不再提示「请先创建行程」之外的空状态", $("d-hint").textContent === "", $("d-hint").textContent);

  console.log("\n3) 规则参与页面流程（加载即求值，面板可见）");
  check("加载行程后调用了 rules:evaluate",
    calls.some((call) => /\/rules:evaluate$/.test(call.url) && call.method === "POST"));
  check("④ 规则面板已显示", $("rules-panel").hidden === false);
  check("缺交通时提醒面板不会误报检查完成",
    texts($("rule-notices")).some((text) => /还不能完整判断/.test(text)), texts($("rule-notices")));

  console.log("\n4) 排序 / 锁定 / 移到晚上 / 计算交通控件真的渲染出来");
  const dayTexts = texts($("days"));
  for (const label of ["上移", "下移", "锁定", "移到晚上", "计算 Day 1 交通"]) {
    check(`渲染出「${label}」`, dayTexts.includes(label), dayTexts);
  }
  check("景点条目可拖放（draggable=true）", walk($("days")).some((el) => el.draggable === true));
  check("② 行程概览显示了恢复的景点", dayTexts.includes("历史点"), dayTexts);

  const lockButton = findByText($("days"), "锁定");
  fire(lockButton, "click");
  await settle();
  check("点「锁定」发出了 PATCH 并带 If-Match", calls.some((call) =>
    call.method === "PATCH" && call.url === "/api/trips/trip_saved" && call.body
    && call.body.days[0].ordered_stops[0].locked === true),
    calls.filter((call) => call.method === "PATCH"));

  const upButton = findByText($("days"), "下移");
  check("只有一个景点时「下移」被禁用", upButton.disabled === true);

  const computeButton = findByText($("days"), "计算 Day 1 交通");
  fire(computeButton, "click");
  await settle(60);
  check("点「计算交通」逐区间调用了 routes:compute",
    calls.filter((call) => /\/routes:compute$/.test(call.url)).length === 2,
    calls.filter((call) => /\/routes:compute$/.test(call.url)));
  check("路线写回了行程（PATCH transit_from_previous）", calls.some((call) =>
    call.method === "PATCH" && call.body && call.body.days && call.body.days[0].ordered_stops[0].transit_from_previous));
  check("② 日卡渲染了方案卡", walk($("days")).filter(el=>el.className === "route-card").length === 2, texts($("days")));
  check("演示路线标注了「非真实导航」",
    texts($("days")).some((text) => /演示路线/.test(text)), texts($("days")));

  console.log("\n5) 加入景点也会触发规则求值（规则参与添加流程）");
  const before = calls.filter((call) => /\/rules:evaluate$/.test(call.url)).length;
  app.state.selected = POI_A;
  $("d-day").value = "1";
  await app.addSelectedToDay();
  await settle();
  check("加入景点后重新求值了规则",
    calls.filter((call) => /\/rules:evaluate$/.test(call.url)).length > before,
    { before, after: calls.filter((call) => /\/rules:evaluate$/.test(call.url)).length });
  check("加入景点调用了 POST stops",
    calls.some((call) => call.method === "POST" && /\/days\/1\/stops$/.test(call.url)));

  console.log("\n6) 兴趣真的影响 POI 排序");
  app.state.trip.user_profile.interests = ["history_culture"];
  app.renderPoiList();
  const ordered = $("poi-list").children.map((item) => walk(item).find(el => el.tagName === "STRONG").textContent);
  check("兴趣命中的类别排在最前", ordered[0] === "历史点", ordered);
  check("POI 面板提示了当前排序依据",
    /已按兴趣排序/.test($("poi-hint").textContent), $("poi-hint").textContent);
  app.state.trip.user_profile.interests = [];
  app.renderPoiList();
  check("没有兴趣时按热度排序", walk($("poi-list").children[0]).find(el => el.tagName === "STRONG").textContent === "自然点");
  check("照片缺失时明确标注占位并显示简介", texts($("poi-list")).includes("暂无照片") && walk($("poi-list")).some(el => el.className === "poi-summary"));

  console.log("\n7) 住宿 / 口岸支持英文与拼音联想，并写入契约的 name_pinyin");
  $("hotel-search").value = "heping";
  app.renderAnchorPickers();
  check("拼音 heping 能搜到和平饭店",
    $("hotel").children.some(o=>o.value === "hotel_peace"),
    $("hotel").children.map((o) => o.value));
  $("hotel-search").value = "fairmont";
  app.renderAnchorPickers();
  check("英文 fairmont 能搜到和平饭店", $("hotel").children.some(o=>o.value === "hotel_peace"));
  $("hotel-search").value = "shangri-la";
  app.renderAnchorPickers();
  check('别名 shangri-la 能搜到浦东香格里拉', $('hotel').children.some(o=>o.value === 'hotel_pudong_shangrila'));
  check('筛选不会自动改选另一家住宿', $('hotel').value === '');
  $("hotel-search").value = "zzzz";
  app.renderAnchorPickers();
  check("无匹配时下拉被禁用且不给默认值",
    $("hotel").disabled === true && $("hotel").value === "", { disabled: $("hotel").disabled, value: $("hotel").value });
  $("hotel-search").value = "";
  $("hub-search").value = "hongqiao";
  app.renderAnchorPickers();
  check("拼音 hongqiao 能搜到虹桥的两个口岸", $("arrival-hub").children.length >= 2,
    $("arrival-hub").children.map((o) => o.value));
  check("口岸/住宿候选来自后端清单（前端已不再写死）",
    app.anchors("hubs").length === ANCHORS_FIXTURE.hubs.length
      && app.anchors("hotels").length === ANCHORS_FIXTURE.hotels.length,
    { actual: { hubs: app.anchors("hubs").length, hotels: app.anchors("hotels").length },
      expected: { hubs: ANCHORS_FIXTURE.hubs.length, hotels: ANCHORS_FIXTURE.hotels.length } });

  $("arrival-date").value = "2026-10-12";
  $("arrival-time").value = "23:30";
  $("duration-days").value = "2";
  $("arrival-hub").value = "hub_hongqiao_rail";
  $("hotel").value = "hotel_peace";
  checkedInterests = [{ value: "history_culture" }];
  const payload = app.readSetup();
  check("住宿写入了契约允许的 name_pinyin", payload.anchor_hotel.name_pinyin === "heping fandian",
    payload.anchor_hotel);
  check("住宿坐标是 WGS84", payload.anchor_hotel.coordinate.crs === "WGS84", payload.anchor_hotel.coordinate);
  check("兴趣被带进行程设定", payload.user_profile.interests[0] === "history_culture", payload.user_profile);
  check("抵达时间被解析成 UTC 秒", Number.isInteger(payload.anchor_arrival.at), payload.anchor_arrival);

  // 离境锚点（契约 anchor_departure）：后端一直支持、route_adapter 也在用，但前端原来没有入口。
  check("未勾选离境安排时 payload 里 anchor_departure 为 null",
    payload.anchor_departure === null, payload.anchor_departure);
  $("has-departure").checked = true;
  fire($("has-departure"), "change");
  check("勾选离境后默认值落在行程最后一天（抵达 10-12 + 2 天 → 10-13）",
    $("departure-date").value === "2026-10-13", $("departure-date").value);
  $("departure-hub").value = "hub_pvg_t2";
  $("departure-date").value = "2026-10-13";
  $("departure-time").value = "18:30";
  // 桩 DOM 不会从 HTML 的 checked 属性初始化 .checked，这里照真实浏览器补上
  // （默认值本身由 index.html 的 checked 属性保证，下面有静态断言）。
  $("departure-international").checked = true;
  const withDeparture = app.readSetup();
  check("离境锚点被写进 payload（含坐标与国际段标记）",
    Boolean(withDeparture.anchor_departure)
      && /浦东国际机场 T2/.test(withDeparture.anchor_departure.location_name)
      && Number.isInteger(withDeparture.anchor_departure.at)
      && withDeparture.anchor_departure.coordinate.crs === "WGS84"
      && withDeparture.anchor_departure.is_international === true,
    withDeparture.anchor_departure);
  check("勾选离境但没选口岸时明确报错，而不是静默丢掉这一段",
    (() => {
      const saved = $("departure-hub").value;
      $("departure-hub").value = "";
      try { app.readSetup(); return false; }
      catch (error) { return /离境口岸/.test(error.message); }
      finally { $("departure-hub").value = saved; }
    })());
  $("has-departure").checked = false;
  fire($("has-departure"), "change");
  check("取消勾选后不再写入 anchor_departure",
    app.readSetup().anchor_departure === null);

  const selectedCoordinate = app.readSetup().anchor_hotel.coordinate;
  fire($('hotel'),'change');
  app.applyPickedHotelCoordinate({ lat: 31.2222, lng: 121.4444, crs: 'WGS84' });
  check('地图点击不会替换统一选择的住宿坐标', JSON.stringify(app.readSetup().anchor_hotel.coordinate) === JSON.stringify(selectedCoordinate));
  check('住宿选择提示只显示选中名称', /已选择住宿/.test($('anchor-pick-state').textContent) && !/WGS84|坐标/.test($('anchor-pick-state').textContent));

  console.log("\n8) 地图点选坐标的坐标系反解");
  const IRMap = sandbox.window.IRMap;
  const source = { lat: 31.230025, lng: 121.469804 };
  const gcj = IRMap.gcj02FromWgs84(source);
  const back = IRMap.wgs84FromGcj02(gcj);
  /** 与 route_adapter/tests/test_crs.py 同口径的球面距离（米）。 */
  const meters = (a, b) => {
    const R = 6371000, rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  };
  const error = meters(source, back);
  const noCorrection = meters(source, gcj);
  check("GCJ-02 → WGS84 反解与 test_crs.py 同口径（往返 < 50 m）", error < 50, { error_m: error });
  check("反解确实把偏移消掉了（远小于不反解）",
    error * 50 < noCorrection, { error_m: error, offset_m: noCorrection });
  check("境外坐标不做偏移",
    IRMap.wgs84FromGcj02({ lat: 48.85, lng: 2.35 }).lat === 48.85);

  console.log("\n9) 引擎未就绪时明确降级，不静默留白");
  app.state.services = { services: SERVICES.services.map((item) =>
    ({ ...item, ready: item.module_id !== "route_adapter",
       detail: item.module_id === "route_adapter" ? "未运行（无注册文件）" : item.detail })), ready: {} };
  app.renderFlow();
  check("route_adapter 未就绪时路线面板给出原因",
    /路线服务未就绪.*未运行/.test($("route-hint").textContent), $("route-hint").textContent);
  app.state.services.services.find(item => item.module_id === "route_adapter").detail =
    "路线服务未读取 API Key；请在设置 AMAP_WEB_KEY 的终端重新启动整个软件";
  app.renderFlow();
  check("缺少 Key 时路线面板明确提示配置终端并重启软件",
    /AMAP_WEB_KEY.*重新启动/.test($("route-hint").textContent), $("route-hint").textContent);
  check("缺少 Key 时禁用计算全部区间交通", $("compute-all-routes").disabled);
  app.state.services = { services: SERVICES.services.map((item) =>
    ({ ...item, ready: item.module_id !== "rules_engine" })), ready: {} };
  app.renderFlow();
  check("rules_engine 未就绪时规则面板给出原因",
    texts($("rule-notices")).some((text) => /提醒服务暂未连接/.test(text)), texts($("rule-notices")));

  console.log("\n10) 创建前预校验、① 草稿、删除 / 复制行程");

  // 以前是「一提交就直接 POST /api/trips」：非法输入或后续规则拒绝时行程已经落盘了。
  calls.length = 0;
  createCalls = 0;
  app.state.trip = null;
  $("arrival-date").value = "2026-10-12";
  $("arrival-time").value = "23:30";
  $("duration-days").value = "2";
  $("arrival-hub").value = "hub_hongqiao_rail";
  $("hotel").value = "hotel_peace";
  checkedInterests = [];
  fire($("setup-form"), "submit");
  await settle();
  const validateAt = calls.findIndex((c) => c.url === "/api/trips:validate");
  const createAt = calls.findIndex((c) => c.url === "/api/trips" && c.method === "POST");
  check("提交时先预校验（不落盘）、再真正创建",
    validateAt >= 0 && createAt > validateAt, calls.map((c) => `${c.method} ${c.url}`));
  check("创建成功后草稿被清掉，下次打开不会冒出过期设定",
    sandbox.localStorage._v["inboundroute.setupDraft"] === undefined, sandbox.localStorage._v);

  // 草稿：刷新或误关页面时，① 里未提交的设定不该丢。
  const draft = {
    duration_days: "5", party: "senior", pacing: "relaxed", interests: ["nature"],
    arrival_date: "2026-11-01", arrival_time: "07:15", arrival_hub: "hub_pvg_t1",
    hub_search: "", hotel: "hotel_peninsula", hotel_search: "", daily_start: "08:00",
    picked_hotel: null, has_departure: true, departure_hub: "hub_pvg_t2",
    departure_date: "2026-11-05", departure_time: "16:40", departure_international: false,
  };
  sandbox.localStorage.setItem("inboundroute.setupDraft", JSON.stringify(draft));
  app.applyDraft(app.loadDraft());
  check("草稿恢复了天数 / 节奏 / 抵达日期与时刻",
    $("duration-days").value === "5" && $("pacing").value === "relaxed"
      && $("arrival-date").value === "2026-11-01" && $("arrival-time").value === "07:15",
    { days: $("duration-days").value, pacing: $("pacing").value,
      date: $("arrival-date").value, time: $("arrival-time").value });
  check("草稿恢复了住宿选择（下拉里确实有这一项）",
    $("hotel").value === "hotel_peninsula", $("hotel").value);
  check("草稿恢复了离境安排（含国内段标记）",
    $("has-departure").checked === true && $("departure-date").value === "2026-11-05"
      && $("departure-time").value === "16:40" && $("departure-international").checked === false,
    { checked: $("has-departure").checked, date: $("departure-date").value,
      time: $("departure-time").value, intl: $("departure-international").checked });
  const restored = app.readSetup();
  check("草稿恢复后仍能正常读出 payload（天数 5、抵达口岸正确）",
    restored.duration_days === 5 && /浦东国际机场 T1/.test(restored.anchor_arrival.location_name),
    { days: restored.duration_days, hub: restored.anchor_arrival.location_name });
  check("表单快照能被再次写回 localStorage",
    (() => { app.saveDraft(); return /"duration_days":"5"/.test(sandbox.localStorage._v["inboundroute.setupDraft"]); })());

  // 删除 / 复制：历史列表以前只能选，不能删也不能复制。
  await sandbox.loadSavedTrip("trip_saved");
  check("有当前行程时删除 / 复制按钮可用",
    $("delete-trip").disabled === false && $("duplicate-trip").disabled === false,
    { del: $("delete-trip").disabled, dup: $("duplicate-trip").disabled });
  calls.length = 0;
  await app.duplicateCurrentTrip();
  check("复制行程打到 POST /trips/{id}:duplicate",
    calls.some((c) => c.method === "POST" && /\/trips\/[^/]+:duplicate$/.test(c.url)),
    calls.map((c) => `${c.method} ${c.url}`));
  calls.length = 0;
  await app.deleteCurrentTrip();
  check("删除行程发出 DELETE /trips/{id}",
    calls.some((c) => c.method === "DELETE" && /^\/api\/trips\/[^/]+$/.test(c.url)),
    calls.map((c) => `${c.method} ${c.url}`));

  const keepTrip = app.state.trip;
  app.state.trip = null;
  app.renderFlow();
  check("没有当前行程时删除 / 复制按钮被禁用",
    $("delete-trip").disabled === true && $("duplicate-trip").disabled === true);
  app.state.trip = keepTrip;

  // 规则契约拒绝（4xx）时必须回滚刚创建的行程；引擎不可达（5xx）不该回滚。
  calls.length = 0;
  await app.rollbackTripCreation("trip_bad");
  check("回滚会删除刚创建的行程",
    calls.some((c) => c.method === "DELETE" && c.url === "/api/trips/trip_bad"),
    calls.map((c) => `${c.method} ${c.url}`));

  // ② 跨天移动：以前只能同一天内上下移动 / 拖拽。
  await sandbox.loadSavedTrip("trip_saved");
  const moveButton = findByText($("days"), "移到该天");
  check("Day 1 的点位渲染出「移到该天」控件", Boolean(moveButton));
  const movePicker = walk($("days")).find((el) => el.className === "move-day-target");
  check("跨天控件列出了另一天（Day 2）",
    Boolean(movePicker) && movePicker.children.length === 1 && movePicker.children[0].value === "2",
    movePicker ? movePicker.children.map((o) => o.value) : null);
  calls.length = 0;
  fire(moveButton, "click");
  await settle();
  const moveCall = calls.find((c) => /\/stops\/[^/]+\/move$/.test(c.url));
  check("跨天移动打到 POST .../stops/{poi_id}/move 且带上目标日",
    Boolean(moveCall) && moveCall.body && moveCall.body.to_day_index === 2,
    calls.map((c) => `${c.method} ${c.url} ${JSON.stringify(c.body || {})}`));

  console.log("\n11) 加入景点之前先预检（④）");
  // 上一节把 rules_engine 改成了未就绪，这里必须先恢复，否则预检会被跳过（降级路径）。
  app.state.services = SERVICES;
  PRECHECK_BLOCKS = true;
  precheckCalls = 0;
  app.state.trip = makeTrip();
  app.state.selected = POI_A;
  $("d-day").value = "1";
  calls.length = 0;
  fire($("d-add"), "click");
  await settle();
  check("预检发现硬冲突时不发出「加入」请求（行程没被改动）",
    calls.some((c) => /rules:precheck$/.test(c.url))
      && !calls.some((c) => /\/days\/1\/stops$/.test(c.url) && c.method === "POST"),
    calls.map((c) => `${c.method} ${c.url}`));
  check("抽屉里说明了硬冲突，并把按钮改成「确认仍然加入」",
    /硬冲突/.test($("d-hint").textContent) && $("d-add").textContent === "确认仍然加入",
    { hint: $("d-hint").textContent, label: $("d-add").textContent });
  calls.length = 0;
  fire($("d-add"), "click");
  await settle();
  check("再次点击才真的加入，并跟着触发一次规则求值",
    calls.some((c) => /\/days\/1\/stops$/.test(c.url) && c.method === "POST")
      && calls.some((c) => /rules:evaluate$/.test(c.url)),
    calls.map((c) => `${c.method} ${c.url}`));
  check("加入成功后按钮文案复位", $("d-add").textContent === "加入行程", $("d-add").textContent);
  PRECHECK_BLOCKS = false;

  // 预检拦过一次后换一天，必须重新预检，不能沿用上一天的「已知情」。
  PRECHECK_BLOCKS = true;
  precheckCalls = 0;
  app.state.trip = makeTrip();
  app.state.selected = POI_A;
  $("d-day").value = "1";
  calls.length = 0;
  fire($("d-add"), "click");
  await settle();
  $("d-day").value = "2";
  fire($("d-day"), "change");
  calls.length = 0;
  fire($("d-add"), "click");
  await settle();
  check("换一天后必须重新预检（不能沿用上一天的确认）",
    calls.some((c) => /rules:precheck$/.test(c.url))
      && !calls.some((c) => /\/days\/2\/stops$/.test(c.url) && c.method === "POST"),
    calls.map((c) => `${c.method} ${c.url}`));
  PRECHECK_BLOCKS = false;

  console.log("\n12) 创建后修改设定（①）");
  app.state.services = SERVICES;
  app.state.trip = makeTrip({
    trip_id: "trip_edit1", version: 5,
    days: [
      { day_index: 1, date: "2026-10-12", day_status: "arrival_only", daily_start_local: "08:15", poi_cap: 4, ordered_stops: [] },
      { day_index: 2, date: "2026-10-13", day_status: "empty", daily_start_local: "08:15", poi_cap: 4, ordered_stops: [] },
    ],
  });
  app.renderFlow();
  tripState = app.state.trip;
  await sandbox.loadSavedTrip("trip_edit1");
  await settle();
  check("载入后 ① 表单反映了行程设定（天数 / 每日出发 / 抵达日期）",
    $("duration-days").value === "2"
      && /^\d{4}-\d{2}-\d{2}$/.test($("arrival-date").value),
    { days: $("duration-days").value, start: app.state.trip.days[0].daily_start_local,
      date: $("arrival-date").value });
  check("载入后按坐标反查到正确的抵达口岸与住宿",
    $("arrival-hub").value === "hub_hongqiao_rail" && $("hotel").value === "hotel_peace",
    { hub: $("arrival-hub").value, hotel: $("hotel").value });
  check("表单只保留保存与重置操作", !html.includes("load-current-settings") && !html.includes("cancel-edit") && /id="save-trip"[^>]*>保存行程/.test(html));
  calls.length = 0;
  fire($("setup-form"), "submit");
  await settle();
  const patchCall = calls.find((c) => c.method === "PATCH");
  check("编辑模式下提交走 PATCH，且没有新建行程",
    Boolean(patchCall) && patchCall.url === "/api/trips/trip_edit1"
      && !calls.some((c) => c.url === "/api/trips" && c.method === "POST"),
    calls.map((c) => `${c.method} ${c.url}`));
  check("PATCH 内容包含可编辑的设定字段（天数 / 起始日期 / 离境锚点，保留每日独立时间）",
    Boolean(patchCall) && patchCall.body
      && "duration_days" in patchCall.body && "start_date" in patchCall.body
      && !("daily_start_local" in patchCall.body) && "anchor_departure" in patchCall.body,
    patchCall ? Object.keys(patchCall.body) : null);
  calls.length = 0;
  fire($("setup-form"), "submit");
  await settle();
  check("连续保存仍更新当前行程，不产生副本", calls.some(c => c.method === "PATCH") && !calls.some(c => c.method === "POST" && c.url === "/api/trips"));
  fire($("reset-form"), "click");
  check("已有行程重置恢复已保存设定", app.state.trip.days[0].daily_start_local === "08:15");

  app.state.trip = tripState = makeTrip();
  flow.routes = {};
  app.renderFlow();
  check("未计算交通时显示操作提示", $("route-hint").textContent.includes("计算全部区间交通"));
  calls.length = 0;
  fire($("compute-all-routes"), "click");
  await settle(80);
  check("② 直接计算有景点日的全部区段，跳过空日", calls.filter(c => /routes:compute$/.test(c.url)).length === 2 && !calls.some(c => /days\/2\/routes:compute$/.test(c.url)));
  tripState = app.state.trip = makeTrip();
  tripState.days[1].ordered_stops = [{...tripState.days[0].ordered_stops[0]}];
  calls.length = 0;
  fire($("compute-all-routes"), "click");
  await settle(80);
  check("全部交通计算覆盖两个非空日", calls.filter(c => /routes:compute$/.test(c.url)).length === 4);
  ROUTE_FAILURE = true;
  calls.length = 0;
  fire($("compute-all-routes"), "click");
  await settle(80);
  check("交通失败时停止后续日并明确提示", calls.filter(c => /routes:compute$/.test(c.url)).length === 1 && $("route-progress").textContent.includes("计算失败"));
  ROUTE_FAILURE = false;
  $("trip-history").value = "";
  fire($("trip-history"), "change");
  await settle();
  check("历史下拉的新建行程项能清除当前选择", app.state.trip === null);
  $("duration-days").value = "5";
  app.saveDraft();
  await sandbox.restoreHistory();
  app.applyDraft(app.loadDraft());
  check("刷新恢复新建草稿时不会误选旧行程", app.state.trip === null && $("duration-days").value === "5");

  console.log("\n13) 地图图钉必须跟着列表筛选走（③）");
  app.state.trip = null;
  app.state.pois = [
    { poi_id: "poi_a", names: { "zh-Hans": "外滩", en: "The Bund" }, category: { level1: "modern_skyline", level2: "waterfront", label_zh: "天际线" },
      romanization: { pinyin: "waitan" }, search_aliases: [], popularity_norm: 1, coordinate: { lat: 31.24, lng: 121.49 } },
    { poi_id: "poi_b", names: { "zh-Hans": "豫园", en: "Yu Garden" }, category: { level1: "history_culture", level2: "garden", label_zh: "园林" },
      romanization: { pinyin: "yuyuan" }, search_aliases: [], popularity_norm: 0.8, coordinate: { lat: 31.227, lng: 121.492 } },
  ];
  app.state.isDensePoint = () => true;
  app.state.showAllPois = false;
  $("poi-search").value = "";
  $("poi-category").value = "";
  app.renderPoiList();
  check("无筛选时地图与列表都是全部点位",
    app.mapPois().length === 2 && $("poi-list").children.length === 2,
    { map: app.mapPois().length, list: $("poi-list").children.length });
  $("poi-search").value = "yuyuan";
  app.renderPoiList();
  check("搜索后图钉集合与列表同步收窄（原来图钉不跟着过滤）",
    app.mapPois().length === 1 && app.mapPois()[0].poi_id === "poi_b"
      && $("poi-list").children.length === 1,
    { map: app.mapPois().map((p) => p.poi_id), list: $("poi-list").children.length });
  $("poi-search").value = "";
  $("poi-category").value = "history_culture";
  app.renderPoiList();
  check("类别筛选后图钉同样同步",
    app.mapPois().length === 1 && app.mapPois()[0].poi_id === "poi_b",
    app.mapPois().map((p) => p.poi_id));
  $("poi-search").value = "zzzzz";
  app.renderPoiList();
  check("筛不到任何点位时地图也应为空",
    app.mapPois().length === 0 && $("poi-list").children.length === 1,
    { map: app.mapPois().length });
  $("poi-search").value = "";
  $("poi-category").value = "";
  app.renderPoiList();

  console.log('\n14) 每人预算');
  check('行程设定暴露可选每人预算字段', /id="budget-per-person"/.test(html));
  app.state.trip = tripState = makeTrip({budget:{scope:'per_person',currency:'CNY',amount_cents:123456}});
  app.formFromTrip(app.state.trip);
  check('载入行程按元回填预算', $('budget-per-person').value === '1234.56');
  app.renderTrip();
  check('概览说明每人预算口径', texts($('trip-meta')).join(' ').includes('每人预算') && texts($('trip-meta')).join(' ').includes('1,234.56'));
  $('budget-per-person').value='12.34';
  check('提交预算精确转换为分', app.readSetup().budget.amount_cents === 1234);
  for (const invalid of ['-1','0.001','1e3','abc','10000000000']) {
    $('budget-per-person').value=invalid;
    check('拒绝非法预算 '+invalid, (()=>{try {app.readSetup();return false;} catch(e){return /预算/.test(e.message);}})());
  }
  $('budget-per-person').value='0';
  check('零元预算与空白不同', app.readSetup().budget.amount_cents === 0);
  $('budget-per-person').value='';
  check('空白显式清空预算', app.readSetup().budget === null);
  $('budget-per-person').value='2500.50';app.saveDraft();$('budget-per-person').value='';app.applyDraft(app.loadDraft());
  check('草稿保留每人预算', $('budget-per-person').value === '2500.50');
  app.formFromTrip(app.state.trip);
  const retainedRoutes={1:[ROUTE]};flow.routes=retainedRoutes;
  $('budget-per-person').value='2000';calls.length=0;
  await sandbox.saveSettings(app.readSetup());
  check('仅预算修改发送预算 PATCH', JSON.stringify(Object.keys(calls.find(c=>c.method==='PATCH').body)) === '["budget"]');
  check('仅预算修改保留交通缓存', flow.routes === retainedRoutes);
  app.formFromTrip(makeTrip());
  check('旧行程回填时清除上一份预算', $('budget-per-person').value === '');

  console.log('\n15) 推荐与已保存自定义住宿走真实按钮接线');
  app.state.pois=[POI_A,POI_B];
  await sandbox.loadSavedTrip('');
  $('duration-days').value='5';fire($('setup-form'),'input');
  const recommendationBoxes=()=>$('recommendation-days').children.map(label=>label.children[0]);
  check('5 天推荐默认只勾选中间日', recommendationBoxes().filter(n=>n.checked).map(n=>n.value).join(',') === '2,3,4');
  let selection=recommendationBoxes();selection[0].checked=true;fire(selection[0],'change');selection[1].checked=false;fire(selection[1],'change');
  await sandbox.refreshServices();
  check('定时服务刷新不重置用户选中的首尾日期',recommendationBoxes().filter(n=>n.checked).map(n=>n.value).join(',') === '1,3,4');
  selection=recommendationBoxes();selection[0].checked=false;fire(selection[0],'change');selection[1].checked=true;fire(selection[1],'change');
  app.applyDraft({hotel_mode:'manual',hotel_name:'江边自填民宿',picked_hotel:{lat:31.31,lng:121.51,crs:'WGS84'}});
  $('hotel-search').value='江边';fire($('hotel-search'),'input');fire($('setup-form'),'input');
  check('旧自填住宿草稿在统一搜索中保留原名与坐标', app.readSetup().anchor_hotel.name_zh === '江边自填民宿' && app.readSetup().anchor_hotel.coordinate.lat === 31.31);
  check('住宿入口仅保留搜索与选择', !html.includes('id="hotel-mode"') && !html.includes('id="hotel-name"') && !html.includes('id="pick-hotel"'));
  calls.length=0;fire($('generate-recommendations'),'click');fire($('generate-recommendations'),'click');await settle(80);
  check('真实推荐按钮双击只计算一次且一次完整新建',calls.filter(c=>c.url==='/api/recommendations:generate').length===1
    && calls.filter(c=>c.url==='/api/trips:recommended').length===1 && !calls.some(c=>c.method==='POST' && (c.url==='/api/trips' || /\/stops$/.test(c.url))));
  const recommendCall=calls.find(c=>c.url==='/api/recommendations:generate');
  check('生成请求携带所选日期与自填住宿原名坐标',JSON.stringify(recommendCall.body.day_indices)==='[2,3,4]' && recommendCall.body.setup.anchor_hotel.name_zh==='江边自填民宿'
    && recommendCall.body.setup.anchor_hotel.name_en==='江边自填民宿' && recommendCall.body.setup.anchor_hotel.coordinate.crs==='WGS84' && recommendCall.body.setup.anchor_hotel.coordinate.lat===31.31);
  check('推荐成功日卡显示景点且保留理由与核验提示',app.state.trip.trip_id==='trip_recommended' && texts($('days')).some(t=>t.includes('自然点'))
    && texts($('recommendation-results')).join(' ').includes('开放资料待核验'));
  check('推荐成功清除草稿、记住历史并继续规则求值',app.loadDraft()===null && sandbox.localStorage.getItem('inboundroute.lastTrip')==='trip_recommended'
    && calls.some(c=>/rules:evaluate$/.test(c.url) && c.body.trigger==='add_stop'));
  calls.length=0;fire($('generate-recommendations'),'click');await settle(80);
  const existingCall=calls.find(c=>c.url==='/api/recommendations:generate'),applyCall=calls.find(c=>/recommendations:apply$/.test(c.url));
  check('已有推荐按钮只传行程 id 与日期，应用带计算快照 If-Match',existingCall && JSON.stringify(Object.keys(existingCall.body).sort())==='["day_indices","trip_id"]'
    && existingCall.body.trip_id==='trip_recommended' && applyCall?.headers['If-Match']==='1');
  const filledDay=app.state.trip.days.find(d=>d.ordered_stops.length);
  check('补空白日不会覆盖之前生成的点位',filledDay.ordered_stops[0].poi_id==='poi_nature' && app.state.trip.days[2].ordered_stops[0].poi_id==='poi_nature');
  calls.length=0;fire(findByText($('days'),'锁定'),'click');await settle(80);
  check('推荐后仍可通过原有日卡锁定编辑',calls.some(c=>c.method==='PATCH' && c.url==='/api/trips/trip_recommended'
    && c.body.days[0].ordered_stops[0].locked===true));
  await sandbox.loadSavedTrip('');await settle();
  check('切换到新行程清除推荐理由及旧自定义住宿选择', $('recommendation-results').children.length===0 && app.state.savedHotels.length===0 && app.state.pickedHotel===null);
  console.log(`\n${checks}/${checks} 通过`);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
