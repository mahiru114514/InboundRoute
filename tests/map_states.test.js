// map.js 纯函数单测：图钉 5 态状态机 + GCJ-02 转换 + 多天角标
// 运行：node tests/map_states.test.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const failures = [];
function check(label, condition, detail = "") {
  console.log((condition ? "PASS  " : "FAIL  ") + label + (detail ? " :: " + detail : ""));
  if (!condition) failures.push(label);
}

// 在最小沙箱里加载 map.js（它只在顶层用到 window）
const source = fs.readFileSync(path.join(__dirname, "..", "modules", "web_workbench", "web", "map.js"), "utf8");
const makeNode = () => ({
  classList: { add() {}, remove() {}, toggle() {} },
  style: {}, dataset: {}, children: [],
  addEventListener() {}, removeEventListener() {},
  append(child) { this.children.push(child); },
  appendChild(child) { this.children.push(child); },
  setAttribute() {}, remove() {},
});
const sandbox = {
  window: {},
  document: { createElement: makeNode, head: makeNode() },
  location: { origin: "http://127.0.0.1:1" },
  console,
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const IRMap = sandbox.window.IRMap;
check("map.js 暴露 IRMap", Boolean(IRMap && IRMap.poiPinState && IRMap.gcj02FromWgs84));

const { PIN_STATE, poiPinState, poiDayBadge, gcj02FromWgs84 } = IRMap;

function tripWith(stopsByDay, notices) {
  return {
    days: Object.entries(stopsByDay).map(([dayIndex, poiIds]) => ({
      day_index: Number(dayIndex),
      ordered_stops: poiIds.map((poiId) => ({
        poi_id: poiId,
        rule_notices: notices && notices[poiId] ? notices[poiId] : [],
      })),
    })),
  };
}

// ---------------------------------------------------------------- 5 态
const trip = tripWith({ 1: ["a"], 2: ["b", "c"], 3: ["b"] });
check("未加入任何一天 → default",
  poiPinState("z", trip, 1, null) === PIN_STATE.DEFAULT, poiPinState("z", trip, 1, null));
check("无行程时一律 default",
  poiPinState("a", null, 1, null) === PIN_STATE.DEFAULT, poiPinState("a", null, 1, null));
check("已加入当前天但未选中 → added_current_day_unselected",
  poiPinState("b", trip, 2, null) === PIN_STATE.ADDED_CURRENT_DAY_UNSELECTED,
  poiPinState("b", trip, 2, null));
check("已加入当前天且被选中 → selected_current_day",
  poiPinState("c", trip, 2, "c") === PIN_STATE.SELECTED_CURRENT_DAY,
  poiPinState("c", trip, 2, "c"));
check("已加入其他天 → added_other_day",
  poiPinState("a", trip, 2, null) === PIN_STATE.ADDED_OTHER_DAY, poiPinState("a", trip, 2, null));
check("选中的点若不在当前天，仍算 other_day",
  poiPinState("a", trip, 2, "a") === PIN_STATE.ADDED_OTHER_DAY,
  poiPinState("a", trip, 2, "a"));

const conflictTrip = tripWith({ 2: ["d"] }, { d: [{ severity: "hard", outcome: "confirmed_proceed" }] });
check("已确认硬冲突 → added_conflict_warned",
  poiPinState("d", conflictTrip, 2, null) === PIN_STATE.ADDED_CONFLICT_WARNED,
  poiPinState("d", conflictTrip, 2, null));
const pendingTrip = tripWith({ 2: ["d"] }, { d: [{ severity: "hard", outcome: "pending" }] });
check("仅 pending 的硬冲突不算警告态（还需用户确认）",
  poiPinState("d", pendingTrip, 2, null) === PIN_STATE.ADDED_CURRENT_DAY_UNSELECTED,
  poiPinState("d", pendingTrip, 2, null));

const multiDay = tripWith({ 2: ["e"], 5: ["e"] });
check("同一 POI 出现在多天 → 角标列出所有天",
  poiDayBadge(multiDay, "e") === "D2/D5", poiDayBadge(multiDay, "e"));
check("未加入的点没有角标", poiDayBadge(multiDay, "z") === "", poiDayBadge(multiDay, "z"));
check("无行程时没有角标", poiDayBadge(null, "e") === "", poiDayBadge(null, "e"));

// ---------------------------------------------------------------- 坐标转换
const wgs = { lat: 31.2397, lng: 121.49 };            // 外滩
const gcj = gcj02FromWgs84(wgs);
const dLat = Math.abs(gcj.lat - wgs.lat), dLng = Math.abs(gcj.lng - wgs.lng);
check("WGS84 → GCJ-02 有偏移且量级合理（0.001~0.01 度）",
  dLat > 0.0005 && dLat < 0.01 && dLng > 0.0005 && dLng < 0.01,
  `Δlat=${dLat.toFixed(5)} Δlng=${dLng.toFixed(5)}`);
check("上海（国内）必须发生偏移", dLat > 0 && dLng > 0);
const overseas = gcj02FromWgs84({ lat: 51.5007, lng: -0.1246 });   // 伦敦
check("境外坐标不偏移（outOfChina 判定）",
  overseas.lat === 51.5007 && overseas.lng === -0.1246, JSON.stringify(overseas));

// ---------------------------------------------------------------- 视野计算（密集簇 + 锚点避让）
const { approxKm, densestCluster, anchorOffset, collectPins } = IRMap;
check("approxKm 对已知距离量级正确", (() => {
  const d = approxKm({ lat: 31.2397, lng: 121.49 }, { lat: 31.2335, lng: 121.4789 }); // 外滩↔酒店约 1.2km
  return d > 0.8 && d < 1.8;
})(), approxKm({ lat: 31.2397, lng: 121.49 }, { lat: 31.2335, lng: 121.4789 }).toFixed(2) + " km");

// 模拟真实数据：3 个市中心点 + 1 个 30km 外的远郊点
const centre = [
  { lat: 31.2397, lng: 121.4900 },   // 外滩
  { lat: 31.2286, lng: 121.4751 },   // 上海博物馆
  { lat: 31.2272, lng: 121.4921 },   // 豫园
];
const faraway = { lat: 31.1111, lng: 121.0533 };   // 朱家角，约 30km
const cluster = densestCluster([...centre, faraway], 15);
check("密集簇只含市中心 3 个点（排除远郊点）", cluster.length === 3 && !cluster.includes(faraway),
  `簇内 ${cluster.length} 个，含远郊=${cluster.includes(faraway)}`);
check("只有两个点时原样返回", densestCluster(centre.slice(0, 2), 15).length === 2);
check("全都在一簇时返回全部", densestCluster(centre, 15).length === 3);
// 造两组清晰分离的点：市中心 3 个（紧凑），远郊 3 个（朱家角一带，距市中心约 40km）
const farGroup = [
  { lat: 31.1111, lng: 121.0533 },   // 朱家角古镇
  { lat: 31.1200, lng: 121.0600 },
  { lat: 31.1050, lng: 121.0450 },
];
const minGap = Math.min(...centre.flatMap((a) => farGroup.map((b) => approxKm(a, b))));
check("测试数据本身：两组之间确实超过 15km（否则合并才是正确行为）", minGap > 15,
  `最近跨组距离 ${minGap.toFixed(1)} km`);

const picked = densestCluster([...centre, ...farGroup], 15);
const pickedDiameter = picked.length > 1
  ? Math.max(...picked.flatMap((a) => picked.map((b) => approxKm(a, b)))) : 0;
check("返回的簇内部两两跨度不超过 gapKm（核心不变量）", pickedDiameter <= 15,
  `直径 ${pickedDiameter.toFixed(1)} km`);
check("两组都是 3 个点时取更紧凑的市中心那簇（1.65km vs 1.83km）",
  picked.length === 3 && picked.every((point) => centre.some((c) => c.lat === point.lat)),
  `取到 ${picked.length} 个，直径 ${pickedDiameter.toFixed(2)} km`);

// 给远郊补一个点 → 4 个 vs 3 个，应当改取远郊那簇
const biggerPicked = densestCluster([...centre, ...farGroup, { lat: 31.1150, lng: 121.0560 }], 15);
check("一簇明显更大时取大的那簇（4 个远郊点 vs 3 个市中心点）",
  biggerPicked.length === 4 && !biggerPicked.some((point) => centre.some((c) => c.lat === point.lat)),
  `取到 ${biggerPicked.length} 个`);

const chained = [{ lat: 31.2397, lng: 121.49 }, { lat: 31.25, lng: 121.50 }, { lat: 31.1111, lng: 121.0533 }];
check("判据是「两两都近」：不能靠中间点把 30km 外的点链进来",
  densestCluster(chained, 15).length === 2, densestCluster(chained, 15).length);

const anchor = { lat: 31.2335, lng: 121.4789 };     // 酒店，离外滩约 1.25km
check("锚点离最近 POI 超过阈值（400m）时不动", anchorOffset(anchor, centre).lat === anchor.lat,
  `${approxKm(anchor, centre[0]).toFixed(2)} km`);
const overlapping = { lat: 31.2398, lng: 121.4901 };  // 几乎和外滩重合
const moved = anchorOffset(overlapping, centre);
check("锚点与最近 POI 几乎重合时被推开 (>300m)",
  approxKm(moved, overlapping) > 0.3 && approxKm(moved, centre[0]) > approxKm(overlapping, centre[0]),
  `推开 ${(approxKm(moved, overlapping) * 1000).toFixed(0)} m`);
check("没有 POI 时锚点不动", anchorOffset(anchor, []).lat === anchor.lat);

// collectPins 需要 POI 形状的对象（有 coordinate 与 names），这里包一层
const asPois = (points) => points.map((coordinate, index) => ({
  poi_id: `p${index}`, coordinate, names: { "zh-Hans": `点${index}` },
}));

const anchorPins = collectPins(asPois(centre), anchor, null, 1, null, () => {}, { showAnchor: true });
check("showAnchor=true 时锚点在集合里", anchorPins.some((pin) => pin.key === "__anchor__"));
const noAnchorPins = collectPins(asPois(centre), anchor, null, 1, null, () => {}, { showAnchor: false });
check("showAnchor=false 时不放锚点（全览模式）", !noAnchorPins.some((pin) => pin.key === "__anchor__"));
check("锚点层级高于所有 POI 图钉",
  Math.max(...noAnchorPins.map((pin) => pin.zIndex)) <
  Math.max(...anchorPins.map((pin) => pin.zIndex)),
  `${Math.max(...anchorPins.map((pin) => pin.zIndex))} vs ${Math.max(...noAnchorPins.map((pin) => pin.zIndex))}`);

console.log("\n" + (failures.length ? `失败 ${failures.length} 项：${failures.join("; ")}` : "全部通过"));
process.exit(failures.length ? 1 : 0);
