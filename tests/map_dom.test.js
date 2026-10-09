"use strict";
/* 回归测试：示意地图 ↔ 真实底图来回切换时，#map-label 不能被弄丢。
 *
 * 背景（真实 bug）：renderSketchMap() 用 replaceChildren 重建 #sketch-map 的内容，
 * 顺手把静态 HTML 里的 <span id="map-label"> 删掉了；之后 initMap() 再执行到
 *   $("map-label").textContent = ...
 * 就抛 TypeError: Cannot set properties of null —— 地图只初始化了一半，白屏。
 *
 * 本测试不依赖 jsdom：用最小可用的假 DOM 真正执行 map_view.js 里的两个函数。
 *   node tests/map_dom.test.js
 */

const fs = require("fs");
const path = require("path");

const MAP_VIEW_JS = path.join(__dirname, "..", "modules", "web_workbench", "web", "map_view.js");
const INDEX_HTML = path.join(__dirname, "..", "modules", "web_workbench", "web", "index.html");
const STYLE_CSS = path.join(__dirname, "..", "modules", "web_workbench", "web", "style.css");

let failures = 0;
let checks = 0;

function check(name, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name}${detail ? ` -> ${detail}` : ""}`);
  }
}

/* ------------------------------------------------------------------ 假 DOM */

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.id = "";
    this.className = "";
    this.textContent = "";
    this.title = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.style = {};
    this.classList = {
      _set: new Set(),
      add: (c) => this.classList._set.add(c),
      remove: (c) => this.classList._set.delete(c),
      contains: (c) => this.classList._set.has(c),
    };
  }

  get classList_() { return this.classList; }

  append(...nodes) {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
      index(node);
    }
  }

  replaceChildren(...nodes) {
    for (const child of this.children) unindex(child);
    this.children = [];
    this.append(...nodes);
  }

  addEventListener() { /* 本测试不触发事件 */ }

  /** 深度优先查找后代，供 getElementById 兜底。 */
  findById(id) {
    for (const child of this.children) {
      if (child.id === id) return child;
      const found = child.findById ? child.findById(id) : null;
      if (found) return found;
    }
    return null;
  }
}

/** 只给「已挂到 DOM 上」的元素登记 id —— 这正是原 bug 的关键（被删掉的元素查不到）。 */
const byId = new Map();

function index(node) {
  let root = node;
  while (root.parentNode) root = root.parentNode;
  if (root.__isDocument) collect(root);
}

function collect(node) {
  if (node.id) byId.set(node.id, node);
  for (const child of node.children || []) collect(child);
}

function unindex(node) {
  if (node.id && byId.get(node.id) === node) byId.delete(node.id);
  for (const child of node.children || []) unindex(child);
}

/** 把 index.html 里真实的地图区域结构解析成假 DOM。
 *
 *  这里刻意不做成「几个平级元素」的简化模型：标签的父节点到底是 .map-wrap
 *  还是 #sketch-map，正是「标签会不会跟着地图飘」的关键，必须按真实结构建。
 */
function parseMapRegion(html) {
  const doc = new FakeElement("body");
  doc.__isDocument = true;

  const wrap = new FakeElement("div");
  wrap.className = "map-wrap";
  doc.append(wrap);

  // 按真实结构摆放：label 与 sketch-map 平级、同在 .map-wrap 下，toggle 也是；hint 在外层。
  const layout = [
    ["map-label", "span", wrap],
    ["sketch-map", "div", wrap],
    ["map-toggle", "button", wrap],
    ["map-hint", "p", doc],
  ];
  for (const [id, tag, parent] of layout) {
    if (!new RegExp(`id="${id}"`).test(html)) throw new Error(`index.html 里找不到 id="${id}"`);
    const el = new FakeElement(tag);
    el.id = id;
    parent.append(el);
  }
  return doc;
}

/** 从 index.html 里切出 <div class="map-wrap"> … </div> 这一段（用于结构断言）。 */
function extractMapWrapBlock(html) {
  const start = html.indexOf('class="map-wrap"');
  if (start < 0) return "";
  const open = html.lastIndexOf("<div", start);
  const close = html.indexOf("</div>", html.indexOf('id="map-toggle"'));
  return close < 0 ? html.slice(open) : html.slice(open, close + 6);
}

/* ---------------------------------------------------- 从 map_view.js 抠出待测函数 */

function extractFunction(source, signature) {
  const start = source.indexOf(signature);
  if (start < 0) throw new Error(`找不到函数：${signature}`);
  let depth = 0;
  let seenBrace = false;
  for (let i = start; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === "{") { depth += 1; seenBrace = true; }
    else if (ch === "}") {
      depth -= 1;
      if (seenBrace && depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`函数体未闭合：${signature}`);
}

const mapSource = fs.readFileSync(MAP_VIEW_JS, "utf8");
const htmlSource = fs.readFileSync(INDEX_HTML, "utf8");
const cssSource = fs.readFileSync(STYLE_CSS, "utf8");

/** 取出某条 CSS 规则的声明块正文（按完整选择器精确匹配，避免误取同名前缀）。 */
function cssRule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // 选择器可能出现在行首、其它规则之后，或逗号分隔的选择器列表末尾。
  // 负向回顾 (?<![\w-]) 保证匹配的是完整选择器而不是某个前缀。
  const match = new RegExp(`(?<![\\w-])${escaped}\\s*\\{([^}]*)\\}`, "m").exec(cssSource);
  return match ? match[1] : null;
}

function cssValue(selector, property) {
  const body = cssRule(selector);
  if (body === null) return null;
  const match = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`).exec(body);
  return match ? match[1].trim() : null;
}

/* ------------------------------------------------------------------ 测试 */

console.log("map_dom.test.js\n");

console.log("1) 静态 HTML 必须提供 #map-label，且不能被放进 Leaflet 坐标系里");
check("index.html 含 id=\"map-label\"", /id="map-label"/.test(htmlSource));
check("index.html 含 id=\"sketch-map\"", /id="sketch-map"/.test(htmlSource));
{
  const wrapBlock = extractMapWrapBlock(htmlSource);
  check(".map-wrap 里同时有 #map-label 与 #sketch-map",
    /id="map-label"/.test(wrapBlock) && /id="sketch-map"/.test(wrapBlock));
  // 原 bug 的孪生问题：label 作为 #sketch-map 的子节点会跟着地图平移/缩放一起飘
  check("#map-label 不是 #sketch-map 的子节点",
    !/id="sketch-map"[^>]*>\s*<span[^>]*id="map-label"/.test(htmlSource));
  check("#sketch-map 已是空容器（子节点由脚本填充）",
    /id="sketch-map"[^>]*>\s*<\/div>/.test(htmlSource));
}

console.log("\n2) 布局：上下排列，地图独占整宽并拿到足够高度");
{
  // CSS 括号配平（手工编辑 CSS 最容易踩的坑）
  const opens = (cssSource.match(/\{/g) || []).length;
  const closes = (cssSource.match(/\}/g) || []).length;
  check("style.css 花括号配平", opens === closes, `{ ${opens} 个 / } ${closes} 个`);

  const layoutDisplay = String(cssValue(".poi-layout", "display") || "");
  const layoutDir = String(cssValue(".poi-layout", "flex-direction") || "");
  const layoutCols = cssValue(".poi-layout", "grid-template-columns");
  check(".poi-layout 是上下排列（不再是左右分栏）",
    layoutDisplay === "flex" && layoutDir === "column" && layoutCols === null,
    `display:${layoutDisplay} flex-direction:${layoutDir} 分栏:${layoutCols}`);

  const mapHeight = cssValue(".sketch-map", "height");
  const heightPx = mapHeight && /^(\d+)px$/.exec(mapHeight);
  check("地图有明确高度（否则 Leaflet 会塌成 0）", Boolean(heightPx), String(mapHeight));
  check("地图高度足够大（>= 480px）", Boolean(heightPx) && Number(heightPx[1]) >= 480, String(mapHeight));

  check("POI 列表单行横向滚动", cssValue(".poi-list", "display") === "flex" && cssValue(".poi-list", "overflow-x") === "auto");
  check("离境区块占据整行，内部独立网格", cssValue(".departure", "grid-column") === "1/-1" && cssValue(".departure-fields", "display") === "grid");

  // 地图独占整宽的前提：容器里没有横向分栏，宽度由 main 决定
  check("main 内容区已放宽（>= 1300px）", /max-width:\s*1[3-9]\d\dpx/.test(cssSource),
    String(cssValue("main", "max-width")));
}

console.log("\n3) map_view.js 里的 #map-label 写入必须走 ensureMapLabel()");
{
  const lines = mapSource.split(/\r?\n/);
  const offenders = [];
  lines.forEach((line, i) => {
    // 只看真正的赋值取值：$("map-label").属性 = ...
    if (/\$\("map-label"\)\s*\.\s*\w+\s*=/.test(line)) {
      const ctx = lines.slice(Math.max(0, i - 3), i).join("\n");
      if (!/ensureMapLabel\(\)/.test(ctx)) offenders.push(i + 1);
    }
  });
  check("没有绕过 ensureMapLabel() 的写入", offenders.length === 0, `未防护行：${offenders.join(",")}`);
  check("ensureMapLabel() 已被定义", /function ensureMapLabel\(/.test(mapSource));
  check("renderSketchMap() 只用 ensureMapLabel() 改文字，不再自建 label",
    /ensureMapLabel\(\)\.textContent/.test(mapSource));
}

console.log("\n4) 真实执行 renderSketchMap() → initMap() 两轮，不允许抛错");
(async () => {
  const doc = parseMapRegion(htmlSource);
  const window = { IRMap: null };

  const $ = (id) => doc.findById(id);

  // 最小元素工厂：等价于 map_view.js 里的 element()
  const element = (tag, className, text) => {
    const el = new FakeElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  const state = {
    pois: [
      { poi_id: "a", names: { "zh-Hans": "外滩" }, coordinate: { lat: 31.24, lng: 121.49 } },
      { poi_id: "b", names: { "zh-Hans": "豫园" }, coordinate: { lat: 31.227, lng: 121.492 } },
    ],
    mapConfig: { ready: true, provider: "leaflet", hint: "" },
    map: null, mapPoints: [], densePoints: [], anchor: null,
    isDensePoint: () => true, showAllPois: false, currentDayIndex: 1,
  };

  // ensureMapLabel 在两个函数之间共享，单独抠出来，模拟真实的模块作用域。
  const ensureMapLabel = new Function(
    "$", "element",
    `${extractFunction(mapSource, "function ensureMapLabel(")}\nreturn ensureMapLabel;`,
  )($, element);

  const renderSketchMap = new Function(
    "$", "element", "state", "openDetail", "ensureMapLabel",
    `${extractFunction(mapSource, "function renderSketchMap(")}
     return renderSketchMap;`,
  )($, element, state, () => {}, ensureMapLabel);

  // 记录 initMap 走到的分支，替代真实的 window.IRMap
  const built = { count: 0 };
  window.IRMap = {
    anchorOffset: () => ({ lat: 31.24, lng: 121.49 }),
    densestCluster: (coords) => coords,
    createPicker: () => ({
      kind: "leaflet",
      loadedFrom: "unpkg",
      async load() { return true; },
      onTilesFallback: null,
      build() { built.count += 1; },
    }),
  };

  // initMap 现在通过 mapPois() 取「地图上要画哪些点」（与右侧列表同一套筛选），
  // 并用 visiblePois() 判断「显示全部」开关是否还有意义。两者都注入等价桩：
  // 本用例只关心底图降级路径，不关心筛选。
  const mapPois = () => state.pois;
  const visiblePois = () => state.pois;
  const initMap = new Function(
    "$", "element", "state", "window", "updateMapHint", "anchorPoint", "ensureMapLabel",
    "mapPois", "visiblePois",
    `${extractFunction(mapSource, "async function initMap(")}\nreturn initMap;`,
  )($, element, state, window, () => {}, () => ({ lat: 31.24, lng: 121.49 }), ensureMapLabel,
    mapPois, visiblePois);

  // 第一轮：正常加载真实底图
  try {
    await initMap();
    check("首轮 initMap() 不抛错", true);
  } catch (error) {
    check("首轮 initMap() 不抛错", false, error && error.message);
  }
  check("首轮写入了地图来源文字", /Leaflet/.test($("map-label").textContent), $("map-label").textContent);

  // 第二轮：模拟「底图失败 → 降级示意地图 → 点重试 → 再次 initMap」
  //        这正是线上崩溃的路径：renderSketchMap 会清空 #sketch-map 里的所有子节点
  renderSketchMap();
  check("降级后 #map-label 仍存在", $("map-label") !== null);
  check("降级后 #map-label 写的是示意文案", /示意/.test($("map-label").textContent), $("map-label").textContent);

  const beforeRetry = built.count;
  try {
    await initMap();
    check("重试轮 initMap() 不抛错（原 bug 就在这里）", true);
  } catch (error) {
    check("重试轮 initMap() 不抛错（原 bug 就在这里）", false, error && error.message);
  }
  check("重试轮重新写回真实底图文字", /Leaflet/.test($("map-label").textContent), $("map-label").textContent);
  check("重试轮真正调用了 picker.build()", built.count === beforeRetry + 1, `build 次数 ${built.count}`);

  console.log(`\n${checks - failures}/${checks} 通过`);
  if (failures) process.exit(1);
})().catch((error) => {
  console.error("测试自身出错：", error);
  process.exit(1);
});
