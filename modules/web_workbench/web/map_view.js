"use strict";
/* 示意图/真实底图装配、视野与图钉刷新；依赖 runtime、IRMap 与 poi_list。 */

function renderSketchMap() {
  const map = $("sketch-map");
  map.classList.remove("map-live");
  // label 现在挂在 .map-wrap 上（不在地图坐标系里），不会被下面的 replaceChildren 删掉，
  // 但文字必须改回示意地图，否则会残留「Leaflet 地图」这种误导性说明。
  ensureMapLabel().textContent = "示意地图（未接入真实底图）";
  map.replaceChildren();
  const pois = state.pois;
  if (!pois.length) return;
  const lats = pois.map((poi) => poi.coordinate.lat);
  const lngs = pois.map((poi) => poi.coordinate.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const spanLat = maxLat - minLat || 0.01, spanLng = maxLng - minLng || 0.01;
  for (const poi of pois) {
    const dot = element("button", "pin");
    dot.style.left = `${8 + ((poi.coordinate.lng - minLng) / spanLng) * 84}%`;
    dot.style.top = `${88 - ((poi.coordinate.lat - minLat) / spanLat) * 76}%`;
    dot.title = `${poi.names["zh-Hans"]} · ${poi.coordinate.lat},${poi.coordinate.lng}`;
    dot.textContent = poi.names["zh-Hans"].slice(0, 1);
    dot.addEventListener("click", () => openDetail(poi));
    map.append(dot);
  }
}

/** 取 #map-label；被清掉时按原样式重建。
 *  必须挂在 .map-wrap 上而不是 #sketch-map 里：后者是 Leaflet 的平移坐标系，
 *  放进去标签会跟着地图一起漂。
 *  @returns {HTMLElement}
 */
function ensureMapLabel() {
  let label = $("map-label");
  if (!label) {
    label = element("span", "sketch-label", "");
    label.id = "map-label";
    const host = $("sketch-map") && $("sketch-map").parentNode ? $("sketch-map").parentNode : document.body;
    host.append(label);
  }
  return label;
}

/* ---------------------------------------------------------------- 地图（高德 or 示意） */

/** 初始化地图：按配置选高德 / Leaflet，未配置或加载失败则降级为示意地图。
 *  默认只框住「最密集的一簇」POI（上海尺度大，远郊点会把市中心压成一团），
 *  并提供「显示全部」开关切到全览。
 */
async function initMap() {
  const config = state.mapConfig || { ready: false };
  state.mapPoints = state.pois;
  state.anchor = window.IRMap ? window.IRMap.anchorOffset(anchorPoint(), state.pois) : anchorPoint();
  state.densePoints = window.IRMap
    ? window.IRMap.densestCluster(state.pois.map((poi) => poi.coordinate), 15)
    : state.pois.map((poi) => poi.coordinate);
  const isDense = (coordinate) => state.densePoints.includes(coordinate);
  state.showAllPois = false;

  const picker = window.IRMap ? window.IRMap.createPicker($("sketch-map"), config, {
    onSelectPoi: (poiId) => {
      const poi = state.pois.find((item) => item.poi_id === poiId);
      if (poi) openDetail(poi);
    },
    getTrip: () => state.trip,
    getCurrentDay: () => state.currentDayIndex,
    getSelectedPoi: () => (state.selected ? state.selected.poi_id : null),
    // 地图点选住宿坐标：底图里已经做了 GCJ-02 → WGS84 反解，这里拿到的一定是 WGS84。
    isPicking: () => state.pickTarget === "hotel",
    onPickCoordinate: (point) => applyPickedHotelCoordinate(point),
  }, { showAll: false, showAnchor: true }) : null;

  if (!picker) {
    $("map-hint").textContent = config.hint || "未配置底图，当前使用示意地图。";
    $("map-toggle").hidden = true;
    renderSketchMap();
    return;
  }  const loaded = await picker.load();
  if (!loaded) {
    state.map = null;
    $("map-hint").textContent = `底图加载失败，已降级为示意地图。原因：${picker.loadError || "未知"}。`
      + (config.provider === "amap"
        ? "请检查高德 key、安全密钥与域名白名单。"
        : "点右上角「重试加载」可再试一次（多为 CDN 一次性抖动）。");
    const toggle = $("map-toggle");
    toggle.hidden = false;
    toggle.textContent = "重试加载";
    toggle.dataset.action = "retry";
    renderSketchMap();
    return;
  }
  state.map = picker;
  state.isDensePoint = isDense;
  picker.onTilesFallback = (name) => {
    $("map-hint").textContent = `高德瓦片不可用，已自动切换到备用底图（${name}）；视野与图钉不受影响。`;
  };
  // 兜底：静态 HTML 的 #map-label 可能已被示意地图清掉，这里重建后再写文字。
  const label = ensureMapLabel();
  label.textContent = (picker.kind === "amap" ? "高德地图" : "Leaflet 地图")
    + `（${picker.loadedFrom || "内置"}）`;
  const toggle = $("map-toggle");
  toggle.dataset.action = "view";
  // 只有当前筛选结果里确实存在「市中心之外」的点，这个开关才有意义。
  const matched = visiblePois();
  toggle.hidden = matched.filter((poi) => isDense(poi.coordinate)).length >= matched.length;
  toggle.textContent = "显示全部";
  updateMapHint();
  picker.build(mapPois(), state.anchor);
}

/** 右上角按钮：底图失败时是「重试加载」，正常时是「显示全部 / 只看市中心」。 */
function onMapToggle() {
  if ($("map-toggle").dataset.action === "retry") {
    const toggle = $("map-toggle");
    toggle.disabled = true;
    toggle.textContent = "加载中…";
    $("map-hint").textContent = "正在重新加载底图…";
    initMap().finally(() => { toggle.disabled = false; });
    return;
  }
  toggleMapView();
}

/** 切换「市中心 / 显示全部」。 */
function toggleMapView() {
  if (!state.map) return;
  state.showAllPois = !state.showAllPois;
  $("map-toggle").textContent = state.showAllPois ? "只看市中心" : "显示全部";
  state.map.setView(state.showAllPois);
  state.map.render(mapPois(), state.anchor);
  updateMapHint();
}

/** 提示行：说明当前视野里有哪些点、有多少点被排除了。 */
function updateMapHint() {
  const matched = visiblePois();
  const total = matched.length;
  const hidden = total - matched.filter((poi) => state.isDensePoint(poi.coordinate)).length;
  const filtered = total !== state.pois.length
    ? `当前筛选命中 ${total} / ${state.pois.length} 个 POI；` : "";
  const base = "图钉状态：默认（白） / 已加入当天（浅绿） / 已加入其他天（D 角标） / 当前选中（深绿） / 有冲突（红）。";
  if (state.showAllPois) {
    $("map-hint").textContent = `${filtered}全览模式：已框入全部 ${total} 个 POI；市中心区域被压缩属正常。${base}`;
  } else if (hidden > 0) {
    const names = matched.filter((poi) => !state.isDensePoint(poi.coordinate))
      .map((poi) => poi.names["zh-Hans"]).join("、");
    $("map-hint").textContent = `${filtered}默认聚焦市中心 ${total - hidden} 个点位；${hidden} 个远郊点（${names}）用「显示全部」查看。${base}`;
  } else {
    $("map-hint").textContent = `${filtered}${base}`;
  }
}

/** 住宿锚点：每日起点与终点（无可选数据时退回上海市中心）。 */
function anchorPoint() {
  const hotel = state.trip && state.trip.anchor_hotel;
  return (hotel && hotel.coordinate) || { lat: 31.2335, lng: 121.4789 };
}

function redrawMap(anchor) {
  if (state.map && state.map.ready) {
    // 与右侧列表同一套筛选结果（mapPois 内部已按视野模式裁剪）。
    state.map.render(mapPois(), anchor || state.anchor || anchorPoint());
  } else {
    renderSketchMap();
  }
}
