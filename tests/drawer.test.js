"use strict";
/* A3 POI 详情抽屉：字段 → 文案模板 → 空值降级。
 *
 * 依据：contracts/mappings.json#/drawer_field_map 与
 *       contracts/devdocs/开发者A-开发需求文档.md（A3 节）
 *
 * 为什么必须测：抽屉是"字段缺失就整行消失/显示待确认"的逻辑，
 * 空白和「—」都是不合格输出。这类分支肉眼看页面几乎发现不了
 * （缺失的字段本来就不会出现在屏幕上），只能靠用例钉住。
 *
 * 运行：node tests/drawer.test.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const INDEX_HTML = path.join(__dirname, "..", "modules", "web_workbench", "web", "index.html");

let checks = 0;
let failures = 0;

function check(name, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail !== undefined ? ` -> ${JSON.stringify(detail)}` : ""}`);
  }
}

/* ------------------------------------------------------------------ 假 DOM */

class FakeElement {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.id = "";
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.value = "";
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.dataset = {};
    this.style = {};
    this.classList = {
      _set: new Set(),
      add: (...cs) => cs.forEach((c) => this.classList._set.add(c)),
      remove: (...cs) => cs.forEach((c) => this.classList._set.delete(c)),
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

  replaceChildren(...nodes) {
    this.children = [];
    this.append(...nodes);
  }

  addEventListener() {}
  setAttribute(name, value) { this[name] = value; }
  querySelectorAll() { return []; }
  /** <dialog> 方法：openDetail 会调 showModal() */
  showModal() { this.open = true; }
  close() { this.open = false; }

  /** 与浏览器一致：textContent 拼接所有后代文本。 */
  get textContent() {
    if (this._ownText) return this._ownText;
    return this.children.map((c) => c.textContent || "").join("");
  }

  set textContent(value) {
    this._ownText = value === null || value === undefined ? "" : String(value);
    this.children = [];
  }

  get innerHTML() { return this.children.map((c) => c.outerHTML).join("") || this._ownText || ""; }
  get outerHTML() {
    const cls = this.className ? ` class="${this.className}"` : "";
    return `<${this.tagName.toLowerCase()}${cls}>${this.innerHTML}</${this.tagName.toLowerCase()}>`;
  }
}

/** 按 index.html 里出现的 id 建出桩节点，保证 $() 都能拿到东西。 */
function makeDocument(html) {
  const ids = [...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]);
  const registry = new Map();
  const roots = [];
  for (const id of ids) {
    const el = new FakeElement(id === "sketch-map" ? "div" : "span");
    el.id = id;
    registry.set(id, el);
    roots.push(el);
  }
  const body = new FakeElement("body");
  body.append(...roots);

  const document = {
    body,
    getElementById: (id) => registry.get(id) || null,
    querySelectorAll: () => [],
    createElement: (tag) => new FakeElement(tag),
    head: new FakeElement("head"),
  };
  return { document, registry };
}

/** 按页面顺序加载全部脚本并取回词法作用域（VM 里 const 不挂到 global）。 */
function loadApp() {
  const html = fs.readFileSync(INDEX_HTML, "utf8");
  const { document, registry } = makeDocument(html);
  const sandbox = {
    window: {},
    document,
    location: { origin: "http://127.0.0.1:1" },
    console,
    fetch: () => new Promise(() => {}),   // 永不 resolve：避免 boot() 发起真实网络
    setTimeout: () => 0,
    clearTimeout: () => {},
    setInterval: () => 0,
    alert: () => {},
    Number, Math, JSON, Date, String, Object, Array, Boolean, parseInt, parseFloat, isNaN,
  };
  vm.createContext(sandbox);

  const source = require("../tools/workbench_assets.cjs").scripts
    .map(script => fs.readFileSync(script.path, "utf8")).join("\n");
  const exported = [
    "WEEKDAYS", "WEEKDAYS_EN", "openingClosureText", "dwellText", "hourText",
    "lightUpText", "reservationText", "detailRows", "openDetail",
  ];
  // 追加导出：VM 里顶层 const/function 不会成为 global 属性
  vm.runInContext(`${source}\n;globalThis.__app = {${exported.join(",")}};`, sandbox);
  return { app: sandbox.__app, registry, document };
}

const { app, registry, document } = loadApp();

/** 抽屉渲染后的 { 标签: 文本 }；未渲染的行不会出现。 */
function drawerRows(poi) {
  app.openDetail(poi);
  const rows = registry.get("d-rows");
  const out = {};
  for (const row of rows.children) {
    const label = row.children[0].textContent;
    const value = row.children[1].textContent;
    out[label] = { value, classes: row.className };
  }
  return out;
}

function poiWith(rules, extra) {
  return {
    poi_id: "test_poi",
    names: { "zh-Hans": "测试点", en: "Test POI" },
    romanization: { pinyin: "cè shì diǎn" },
    operating_rules: rules,
    ...(extra || {}),
  };
}

/* ------------------------------------------------------------------ 用例 */

console.log("drawer.test.js\n");
{
  const sourceNotes = drawerRows(poiWith({opening_hours: [], closure_data_status: 'unverified'},
    {tags: ['静安区', '开放与休馆安排待核实', '预约政策待核实', '停留时长为规划参考', '坐标为地点标注点，实际入口待核实']}));
  check('新数据缺失时展示待核实说明', /开放与休馆安排待核实/.test(sourceNotes['数据说明']?.value || ''));
  check('未知预约不误报无需预约', !('预约' in sourceNotes));
  check('参考停留和入口状态明确展示', /规划参考/.test(sourceNotes['数据说明']?.value || '') && /入口待核实/.test(sourceNotes['数据说明']?.value || ''));
}
console.log("1) 三行标头：拼音缺失时隐藏 Line 2，不许用 name 推导");

check("有拼音时显示",
  (app.openDetail(poiWith({})), registry.get("d-name-pinyin").textContent === "cè shì diǎn"));
check("无拼音时隐藏该行",
  (app.openDetail(poiWith({}, { romanization: {} })), registry.get("d-name-pinyin").hidden === true));
check("无拼音时不残留上一次的文本",
  registry.get("d-name-pinyin").textContent === "");

console.log("\n2) Opening & Closure（opening_hours=[] → 隐藏整行）");
{
  const empty = drawerRows(poiWith({ opening_hours: [], closure_data_status: "unknown" }));
  check("opening_hours=[] 时整行隐藏", !("开放与闭馆" in empty), Object.keys(empty));

  const unknown = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], closure_data_status: "unknown" }));
  check("closure_data_status=unknown 显示「闭馆信息待确认」而非隐藏",
    /闭馆信息待确认/.test(unknown["开放与闭馆"]?.value || ""), unknown["开放与闭馆"]);

  const verified = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], closure_data_status: "verified" }));
  check("正常时段逐条渲染", verified["开放与闭馆"]?.value === "09:00 – 17:00", verified["开放与闭馆"]);
  check("verified 不加 warn 样式", !/warn/.test(verified["开放与闭馆"]?.classes || ""), verified["开放与闭馆"]);
  check("unknown 加 warn 样式", /warn/.test(unknown["开放与闭馆"]?.classes || ""), unknown["开放与闭馆"]);

  const weekly = drawerRows(poiWith({
    opening_hours: [{ open: "09:00", close: "17:00" }], closure_data_status: "verified",
    closure_rules: [{ kind: "weekly", weekday: 1 }],
  }));
  check("weekly closure 用契约英文模板 Closed on Monday",
    /Closed on Monday/.test(weekly["开放与闭馆"]?.value || ""), weekly["开放与闭馆"]);

  const nextDay = drawerRows(poiWith({
    opening_hours: [{ open: "22:00", close: "02:00", close_next_day: true }], closure_data_status: "verified",
  }));
  check("跨零点时段标注「次日」", /次日/.test(nextDay["开放与闭馆"]?.value || ""), nextDay["开放与闭馆"]);
}

console.log("\n3) Last Entry（null → 隐藏该行；有值 → \"{time} Last Entry\"）");
{
  const hidden = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], last_entry_time: null }));
  check("last_entry_time=null 时整行隐藏", !("截止入场" in hidden), Object.keys(hidden));

  const shown = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], last_entry_time: "16:00" }));
  check("有值时按契约模板渲染", shown["截止入场"]?.value === "16:00 Last Entry", shown["截止入场"]);
}

console.log("\n4) Light-up Hours（null 或 windows=[] → 隐藏该行）");
{
  const none = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], light_up: null }));
  check("light_up=null 时整行隐藏", !("亮灯时段" in none), Object.keys(none));

  const emptyWindows = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], light_up: { required: true, windows: [] } }));
  check("windows=[] 时整行隐藏", !("亮灯时段" in emptyWindows), Object.keys(emptyWindows));

  const lit = drawerRows(poiWith({
    opening_hours: [{ open: "09:00", close: "17:00" }],
    light_up: { required: true, windows: [{ start: "19:00", close: "23:00", label_zh: "夏季" }] },
  }));
  check("按契约模板 {start} - {close} ({label}) 渲染",
    lit["亮灯时段"]?.value === "19:00 - 23:00 (夏季)", lit["亮灯时段"]);
}

console.log("\n5) Suggested Dwell（缺失 → 默认 90 分钟并标注「参考值」）");
{
  const missing = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }] }));
  check("缺失时给默认值", /90 分钟/.test(missing["建议停留"]?.value || ""), missing["建议停留"]);
  check("缺失时标注「参考值」", /参考值/.test(missing["建议停留"]?.value || ""), missing["建议停留"]);
  check("缺失时带 default-value 样式（与真实数据区分）",
    /default-value/.test(missing["建议停留"]?.classes || ""), missing["建议停留"]);

  const point = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], dwell_time: { kind: "point", minutes: 90 } }));
  check("point 按分钟渲染", point["建议停留"]?.value === "90 分钟", point["建议停留"]);
  check("point 不标注参考值", !/参考值/.test(point["建议停留"]?.value || ""), point["建议停留"]);

  const range = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], dwell_time: { kind: "range", minutes_min: 90, minutes_max: 120 } }));
  check("range 按契约渲染成 \"1.5 - 2 Hours\"", range["建议停留"]?.value === "1.5 - 2 Hours", range["建议停留"]);
  check("range 无小数尾巴（120 分钟 → 2 而不是 2.0）",
    app.hourText(120) === "2" && app.hourText(90) === "1.5", [app.hourText(120), app.hourText(90)]);
}

console.log("\n6) Reservation（三态：缺失隐藏 / false 显示无需预约 / true 显示需提前 N 天）");
{
  const absent = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }] }));
  check("字段缺失时整行隐藏", !("预约" in absent), Object.keys(absent));

  const notRequired = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], reservation_required: false }));
  check("false 显示「无需预约」（false 是明确结论，不能当没信息）",
    notRequired["预约"]?.value === "无需预约", notRequired["预约"]);

  const required = drawerRows(poiWith({
    opening_hours: [{ open: "09:00", close: "17:00" }],
    reservation_required: true, advance_booking_days: 7,
  }));
  check("true + 天数 → 需提前 7 天预约", required["预约"]?.value === "需提前 7 天预约", required["预约"]);

  const requiredNoDays = drawerRows(poiWith({
    opening_hours: [{ open: "09:00", close: "17:00" }],
    reservation_required: true, advance_booking_days: null,
  }));
  check("true 但缺天数 → 至少显示「需预约」并标 warn",
    requiredNoDays["预约"]?.value === "需预约" && /warn/.test(requiredNoDays["预约"]?.classes || ""),
    requiredNoDays["预约"]);
}

console.log("\n7) 落客点（空数组 → 隐藏该行，不显示「—」）");
{
  const none = drawerRows(poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], drop_off_locations: [] }));
  check("无落客点时整行隐藏", !("落客点" in none), Object.keys(none));

  const some = drawerRows(poiWith(
    { opening_hours: [{ open: "09:00", close: "17:00" }] },
    { drop_off_locations: [{ desc_zh: "北京东路圆明园路口", source: "curated" }] },
  ));
  check("有落客点时渲染描述与来源", /北京东路圆明园路口（curated）/.test(some["落客点"]?.value || ""), some["落客点"]);
}

console.log("\n8) 任何行都不允许出现空文本或「—」兜底");
{
  const cases = [
    poiWith({}),
    poiWith({ opening_hours: [], closure_data_status: "unknown" }),
    poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], closure_data_status: "unknown" }),
    poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], light_up: { required: true, windows: [] } }),
    poiWith({ opening_hours: [{ open: "09:00", close: "17:00" }], dwell_time: { kind: "point", minutes: 90 } }),
  ];
  let bad = [];
  for (const poi of cases) {
    const rows = drawerRows(poi);
    for (const [label, cell] of Object.entries(rows)) {
      if (!cell.value || cell.value === "—") bad.push(`${label}=${JSON.stringify(cell.value)}`);
    }
  }
  check("所有渲染出来的行都有真实文案", bad.length === 0, bad);
}

console.log("\n9) 用真实种子数据渲染（后端 poi_seed.py 的实际内容）");
{
  // 这里只校验真实数据是否触发了异常分支，不复制后端数据到前端测试里，
  // 避免同一份字段被两处维护。真实数据驱动的断言放在后端测试中。
  const realPois = JSON.parse(require("node:child_process").execFileSync("python", ["-X", "utf8", "-c",
    "import json; from modules.trip_engine.poi_seed import POIS; print(json.dumps([p for p in POIS if p['poi_id'] in ('sh_poi_00042','sh_poi_00088','sh_poi_00141')],ensure_ascii=False))"],
    {cwd: path.join(__dirname, ".."), encoding:"utf8"}));

  const bund = drawerRows(realPois[0]);
  check("外滩：last_entry_time=null → 隐藏截止入场",
    !("截止入场" in bund), Object.keys(bund));
  check("外滩：reservation_required=false → 显示无需预约",
    bund["预约"]?.value === "无需预约", bund["预约"]);
  check("外滩：range 建议停留 → 1.5 - 2 Hours",
    bund["建议停留"]?.value === "1.5 - 2 Hours", bund["建议停留"]);
  check("外滩：有落客点 → 渲染",
    /北京东路圆明园路口/.test(bund["落客点"]?.value || ""), bund["落客点"]);

  const museum = drawerRows(realPois[1]);
  check("上海博物馆：周一闭馆 → Closed on Monday",
    /Closed on Monday/.test(museum["开放与闭馆"]?.value || ""), museum["开放与闭馆"]);
  check("上海博物馆：last_entry_time → 15:00 Last Entry",
    museum["截止入场"]?.value === "15:00 Last Entry", museum["截止入场"]);
  check("上海博物馆：需预约",
    museum["预约"]?.value === "需预约", museum["预约"]);
  check("上海博物馆：range 120-180 → 2 - 3 Hours",
    museum["建议停留"]?.value === "2 - 3 Hours", museum["建议停留"]);
  check("上海博物馆：verified 不加 warn",
    !/warn/.test(museum["开放与闭馆"]?.classes || ""), museum["开放与闭馆"]);
  const east = drawerRows(realPois.find(p=>p.poi_id==='sh_poi_00141'));
  check('东馆展示常规周二休馆及节日公告说明', /常规周二休馆/.test(east['数据说明']?.value || '') && /节假日/.test(east['数据说明']?.value || ''));
}

console.log(`\n${checks - failures}/${checks} 通过`);
if (failures) process.exit(1);
