"use strict";
/* 共享状态、DOM 工具、API 请求和北京时间格式化；首先加载。 */

/* InboundRoute 行程工作台（零构建：原生 JS + JSDoc 类型注释）
 *
 * 类型来源：contracts/generated/domain.ts（字段名以契约为准）
 * 本文件不使用构建工具；JSDoc 仅用于编辑器提示与自检。
 * 所有引擎调用都经本模块自己的服务器代理，浏览器不接触任何引擎令牌。
 */

/** @typedef {{module_id:string, ready:boolean, base_url:string, health:string, detail:string, purpose:string}} ServiceStatus */
/** @typedef {{poi_id:string, names:Record<string,string>, romanization?:Record<string,string>}} PoiSummary */

const WB = { token: "", base: "" };
const SESSION_PATH = "/api/session";
/** 构建标记：排查「页面是不是旧文件」时看控制台这一行即可。改代码后请同步 +1 并刷新。 */
const APP_BUILD = "workbench/2026-10-v19";
console.info("[workbench] build", APP_BUILD);
const state = {
  /** @type {PoiSummary[]} */ pois: [],
  /** 抵达/离境口岸与住宿候选：由 GET /api/anchors 供给，前端不再写死 */
  /** @type {{hubs:any[],hotels:any[]}} */ anchors: { hubs: [], hotels: [] },
  /** @type {any} */ trip: null,
  /** @type {any} */ selected: null,
  /** @type {any} */ services: { services: [], ready: {} },
  /** @type {any} */ mapConfig: { ready: false, hint: "" },
  /** @type {any} */ map: null,
  /** @type {any} */ mapPoints: [],
  /** @type {any} */ densePoints: [],
  /** @type {any} */ anchor: null,
  /** @type {any} */ isDensePoint: () => true,
  showAllPois: false,
  currentDayIndex: 1,
  /** 地图点选得到的住宿坐标（WGS84）；null 表示用所选住宿自带的坐标 */
  /** @type {any} */ pickedHotel: null,
  /** 当前是否处于「在地图上点选」模式；'hotel' | null */
  /** @type {any} */ pickTarget: null,
  busy: false,
  /** 用户是否手动改过离境日期/时刻；改过就不再自动跟随抵达日期与天数 */
  departureTouched: false,
  setupBaseline: null,
};
let toastTimer;

/* ---------------------------------------------------------------- 基础工具 */

const $ = (id) => document.getElementById(id);

function notify(message, error = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = "toast" + (error ? " error" : "");
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 7000 : 4000);
}

/** 统一请求：自动带工作台令牌，按契约信封解包。 */
async function api(path, options = {}) {
  const init = { method: options.method || "GET", headers: { "X-Workbench-Token": WB.token } };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
    init.headers["Content-Type"] = "application/json";
  }
  if (options.version) init.headers["If-Match"] = String(options.version);
  const response = await fetch(path, init);
  let data = null;
  try { data = await response.json(); } catch (e) { data = null; }
  if (!response.ok || !data || data.ok === false) {
    const payload = (data && data.error) || {};
    const error = new Error(payload.message || `请求失败（HTTP ${response.status}）`);
    // 状态码必须带出去：调用方要区分「契约拒绝（4xx，应当回滚）」与
    // 「引擎不可达（5xx / 网络，属于降级，行程本身没问题）」。
    error.status = response.status;
    error.code = payload.code || "";
    throw error;
  }
  return data.data;
}

/** 秒 → 北京时间 HH:mm。契约规定 *_at 是 UTC 秒、展示按 Asia/Shanghai。 */
function hhmm(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  return new Date(seconds * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Shanghai",
  });
}

/** 秒 → 北京日期 YYYY-MM-DD。 */
function ymd(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  return new Date(seconds * 1000).toLocaleDateString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", timeZone: "Asia/Shanghai",
  }).replace(/\//g, "-");
}

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
/** 英文星期，用于闭馆文案（契约模板 "Closed on {weekday_label_en}"）。ISO：1=周一 */
const WEEKDAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
function weekdayZh(isoDate) {
  const day = new Date(`${isoDate}T00:00:00+08:00`).getDay();  // 0=周日
  return WEEKDAYS[(day + 6) % 7];                              // ISO：1=周一
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (className && /(?:^|\s)(?:poi-initial|stop-name|names-zh|names-en|names-pinyin)(?:\s|$)/.test(className)) node.setAttribute('data-i18n-ignore','');
  if (text !== undefined) node.textContent = text;
  return node;
}
