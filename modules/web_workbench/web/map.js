"use strict";
/* 地图接入层：支持三种底图来源，未配置时降级为示意地图
 *
 *   provider = "amap"     高德 JS API 2.0（需要 key + 安全密钥，官方在线加载）
 *   provider = "leaflet"  Leaflet + 瓦片（默认用高德公共瓦片；完全免费、无需注册与 key）
 *   provider = null       示意地图（纯 CSS 定位，无外部依赖）
 *
 * 契约依据：contracts/enums.json#/pin_state（5 态）、mappings.json#/drawer_field_map
 * 坐标：POI 主数据按契约是 WGS84。高德底图是 GCJ-02，因此用高德瓦片时要转换；
 *      用 OSM 瓦片时不转换（OSM 就是 WGS84/Web Mercator）。
 */

/** 图钉状态（与 contracts/enums.json#/pin_state 一一对应） */
const PIN_STATE = {
  DEFAULT: "default",
  ADDED_CURRENT_DAY_UNSELECTED: "added_current_day_unselected",
  ADDED_OTHER_DAY: "added_other_day",
  SELECTED_CURRENT_DAY: "selected_current_day",
  ADDED_CONFLICT_WARNED: "added_conflict_warned",
};

const PIN_LABEL = {
  default: "未加入",
  added_current_day_unselected: "已加入当天",
  added_other_day: "已加入其他天",
  selected_current_day: "当前选中",
  added_conflict_warned: "有冲突",
};

/** 纯函数：算出某个 POI 当前应该处于哪个图钉状态（可单测）。 */function poiPinState(poiId, trip, currentDayIndex, selectedPoiId) {
  if (!trip) return PIN_STATE.DEFAULT;
  const daysWithPoi = [];
  let conflict = false;
  for (const day of trip.days) {
    for (const stop of day.ordered_stops) {
      if (stop.poi_id !== poiId) continue;
      daysWithPoi.push(day.day_index);
      const notices = stop.rule_notices || [];
      if (notices.some((n) => n.severity === "hard" && n.outcome === "confirmed_proceed")) conflict = true;
    }
  }
  if (!daysWithPoi.length) return PIN_STATE.DEFAULT;
  if (conflict) return PIN_STATE.ADDED_CONFLICT_WARNED;
  if (selectedPoiId === poiId && daysWithPoi.includes(currentDayIndex)) return PIN_STATE.SELECTED_CURRENT_DAY;
  if (daysWithPoi.includes(currentDayIndex)) return PIN_STATE.ADDED_CURRENT_DAY_UNSELECTED;
  return PIN_STATE.ADDED_OTHER_DAY;
}

/** 角标文案：同一 POI 出现在多天时显示 D2/D5。 */
function poiDayBadge(trip, poiId) {
  if (!trip) return "";
  const days = [];
  for (const day of trip.days) {
    if (day.ordered_stops.some((stop) => stop.poi_id === poiId)) days.push(day.day_index);
  }
  return days.map((index) => `D${index}`).join("/");
}

/* ---------------------------------------------------------------- 坐标系

 * 高德底图用 GCJ-02；契约主数据是 WGS84。标准 GCJ-02 偏移算法（境外不偏移）。
 */
const GCJ = {
  a: 6378245.0, ee: 0.00669342162296594323,
  outOfChina(lng, lat) { return !(lng > 73.66 && lng < 135.05 && lat > 3.86 && lat < 53.55); },
  transformLat(x, y) {
    let ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    ret += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
    ret += ((20 * Math.sin(y * Math.PI) + 40 * Math.sin((y / 3) * Math.PI)) * 2) / 3;
    ret += ((160 * Math.sin((y / 12) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30)) * 2) / 3;
    return ret;
  },
  transformLng(x, y) {
    let ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    ret += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
    ret += ((20 * Math.sin(x * Math.PI) + 40 * Math.sin((x / 3) * Math.PI)) * 2) / 3;
    ret += ((150 * Math.sin((x / 12) * Math.PI) + 300 * Math.sin((x / 30) * Math.PI)) * 2) / 3;
    return ret;
  },
};

/** WGS84 → GCJ-02；point 为 {lat,lng}，返回同结构。 */
function gcj02FromWgs84(point) {
  const { lat, lng } = point;
  if (GCJ.outOfChina(lng, lat)) return { lat, lng };
  let dLat = GCJ.transformLat(lng - 105, lat - 35);
  let dLng = GCJ.transformLng(lng - 105, lat - 35);
  const radLat = (lat / 180) * Math.PI;
  let magic = Math.sin(radLat);
  magic = 1 - GCJ.ee * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180) / (((GCJ.a * (1 - GCJ.ee)) / (magic * sqrtMagic)) * Math.PI);
  dLng = (dLng * 180) / ((GCJ.a / sqrtMagic) * Math.cos(radLat) * Math.PI);
  return { lat: lat + dLat, lng: lng + dLng };
}

/** GCJ-02 → WGS84（近似反解，与 route_adapter/crs.py#gcj02_to_wgs84 同式）。
 *
 *  只在「用户在高德底图上点选坐标」时使用：底图是 GCJ-02，而主数据基准必须是 WGS84。
 *  反向用一次正向变换再取镜像，是国内地图通用的近似做法，误差约 1e-5 度（≈1 米），
 *  远小于点选本身的精度。契约要求转换单向发生在入口，这里正是入口。
 */
function wgs84FromGcj02(point) {
  if (GCJ.outOfChina(point.lng, point.lat)) return { lat: point.lat, lng: point.lng };
  const forward = gcj02FromWgs84(point);
  return { lat: point.lat * 2 - forward.lat, lng: point.lng * 2 - forward.lng };
}

/* ---------------------------------------------------------------- 共享的图钉渲染

 * 两种底图共用同一套图钉 DOM 与状态计算，只有"往地图上放什么"不同。
 * 可视角范围 showAll：全览时隐藏锚点（它一定在市中心，被压缩后没意义），只留有意义的 POI。
 */
function pinElement(poi, state, badge, serial) {
  const content = document.createElement("button");
  content.className = `map-pin pin-${state}`;
  content.innerHTML = `<span class="dot">${state === PIN_STATE.SELECTED_CURRENT_DAY && serial ? serial : "•"}</span>`
    + (badge ? `<span class="badge-day">${badge}</span>` : "");
  content.title = `${poi.names["zh-Hans"]} · ${PIN_LABEL[state]}${badge ? ` · ${badge}` : ""}`;
  return content;
}

function anchorElement(label, title) {
  const content = document.createElement("span");
  content.className = "map-anchor";
  const inner = document.createElement("span");     // 内层负责把文字转回来（外层做了 -45° 造型旋转）
  inner.textContent = label;
  content.append(inner);
  content.title = title;
  return content;
}

/** 为每个 POI 与锚点准备渲染所需的数据（与底图无关）。 */
function collectPins(pois, anchor, trip, currentDay, selected, onSelect, options) {
  const opts = options || {};
  const pins = pois.map((poi) => {
    const state = poiPinState(poi.poi_id, trip, currentDay, selected);
    const badge = poiDayBadge(trip, poi.poi_id);
    const stop = trip
      ? ((trip.days.find((day) => day.day_index === currentDay) || { ordered_stops: [] })
          .ordered_stops.find((item) => item.poi_id === poi.poi_id))
      : null;
    const content = pinElement(poi, state, badge, stop ? String(stop.stop_order) : "");
    content.addEventListener("click", () => onSelect(poi.poi_id));
    return { key: poi.poi_id, point: poi.coordinate, content, state, zIndex: state === PIN_STATE.SELECTED_CURRENT_DAY ? 200 : 100 };
  });
  // 锚点：至少一个 POI 在视野内时才显示；全览模式下市中心被压缩，显示它反而添乱
  if (opts.showAnchor !== false && pois.length) {
    pins.push({ key: "__anchor__", point: anchor, content: anchorElement("⌂", "住宿（每日起点/终点）"),
                zIndex: 300, permanent: true });
  }
  return pins;
}

/* ---------------------------------------------------------------- 视野计算

 * 上海的空间尺度很大：把远郊点（朱家角在西北约 30km）和市中心点放进同一视野，
 * 市中心几个点会挤成一团（PRD 1.2 说的「地理尺度失真」）。所以默认只框住**最密集的一簇**，
 * 并用「显示全部」开关让用户主动切到全览。
 */

/** 经纬度差换算成大致公里数（用于判断距离远近，不需要精确）。 */
function approxKm(a, b) {
  const dLat = (a.lat - b.lat) * 111;
  const dLng = (a.lng - b.lng) * 111 * Math.cos(((a.lat + b.lat) / 2) * (Math.PI / 180));
  return Math.sqrt(dLat * dLat + dLng * dLng);
}

/** 找出最密集的一簇点。
 *
 *  判据是「两两都近」（簇内最大跨度 ≤ gapKm），不是「链式连通」。
 *  链式会把「市中心 → 虹桥 → 青浦 → 朱家角」这种渐变分布全并进一簇，
 *  于是远郊点又跑回市中心视野里——那就失去了分簇的意义。
 */
function densestCluster(points, gapKm) {
  if (points.length <= 2) return points.slice();
  const n = points.length;
  const adjacency = points.map((a) => points.map((b) => approxKm(a, b) <= gapKm));
  let best = null;
  for (let i = 0; i < n; i++) {
    const group = [i];
    for (let j = 0; j < n; j++) {
      if (j === i || group.includes(j)) continue;
      if (group.every((k) => adjacency[k][j])) group.push(j);
    }
    const diameter = group.length > 1
      ? Math.max(...group.flatMap((k) => group.map((m) => approxKm(points[k], points[m]))))
      : 0;
    if (!best || group.length > best.group.length ||
        (group.length === best.group.length && diameter < best.diameter)) {
      best = { group, diameter };
    }
  }
  return best.group.map((index) => points[index]);
}

/** 把锚点从最近的 POI 旁推开，避免两个图钉完全重叠（契约要求锚点常驻可见）。
 *  pois 可以是 POI 对象（有 coordinate）或裸坐标，两种都支持。
 */
function coordinateOf(item) {
  return item && item.coordinate ? item.coordinate : item;
}

function anchorOffset(anchor, pois) {
  const points = (pois || []).map(coordinateOf).filter(Boolean);
  if (!points.length) return anchor;
  const nearest = points.reduce((best, point) =>
    (approxKm(point, anchor) < approxKm(best, anchor) ? point : best), points[0]);
  const distance = approxKm(nearest, anchor);
  if (distance > 0.4) return anchor;                 // 离得够远（>400m），图钉不会重叠
  // 沿「背离最近 POI」的方向推开约 350 米
  const dLat = anchor.lat - nearest.lat;
  const dLng = anchor.lng - nearest.lng;
  const norm = Math.sqrt(dLat * dLat + dLng * dLng) || 1;
  return { lat: anchor.lat + (dLat / norm) * 0.0032, lng: anchor.lng + (dLng / norm) * 0.0032 };
}

/* ---------------------------------------------------------------- 高德底图 */

class AMapPicker {
  constructor(container, config, hooks, options) {
    this.container = container;
    this.config = config;
    this.hooks = hooks;
    this.options = options || { showAll: false, showAnchor: true };
    this.map = null;
    this.markers = new Map();
    this.ready = false;
    this.kind = "amap";
    this.loadedFrom = "高德官方 SDK";
  }

  async load() {
    try {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = this.config.loader_url;
        script.onload = resolve;
        script.onerror = () => reject(new Error("SDK 加载失败（可能是 CSP 或网络）"));
        document.head.append(script);
      });
      // 安全密钥：2021-12-02 之后申请的 key 必须配置，且要在 load 之前设置
      window._AMapSecurityConfig = this.config.security_code
        ? { securityJsCode: this.config.security_code }
        : { serviceHost: `${location.origin}/_AMapService` };
      window.AMap = window.AMap || {};
      window.AMap.securityConfig = window._AMapSecurityConfig;
      const modules = await window.AMapLoader.load({
        key: this.config.key,
        version: this.config.version || "2.0",
        plugins: this.config.plugins || [],
      });
      this.AMap = modules || window.AMap;
      return true;
    } catch (error) {
      this.loadError = error.message;
      return false;
    }
  }

  build(pois, anchor) {
    this.map = new this.AMap.Map(this.container, {
      zoom: 12, center: [anchor.lng, anchor.lat], viewMode: "2D", mapStyle: "amap://styles/normal",
    });
    this.ready = true;
    this.container.classList.add("map-live");
    this.#bindPicking();
    this.render(pois, anchor);
  }

  /** 点选模式：把点击位置反解成 WGS84 交给上层（未开启点选时点击不生效）。
   *  高德底图是 GCJ-02，主数据基准是 WGS84，所以这里必须做一次反解。
   */
  #bindPicking() {
    if (!this.map || typeof this.map.on !== "function") return;
    this.map.on("click", (event) => {
      const hooks = this.hooks || {};
      if (!hooks.onPickCoordinate || !hooks.isPicking || !hooks.isPicking()) return;
      const lnglat = event && event.lnglat;
      if (!lnglat) return;
      hooks.onPickCoordinate(wgs84FromGcj02({ lat: lnglat.getLat(), lng: lnglat.getLng() }));
    });
  }

  render(pois, anchor) {
    if (!this.ready) return;
    this.pois = pois;
    this.anchor = anchor;
    const trip = this.hooks.getTrip();
    const pins = collectPins(pois, anchor, trip, this.hooks.getCurrentDay(),
      this.hooks.getSelectedPoi(), this.hooks.onSelectPoi, this.options);
    for (const marker of this.markers.values()) marker.setMap(null);
    this.markers.clear();
    for (const pin of pins) {
      const fixed = gcj02FromWgs84(pin.point);
      const marker = new this.AMap.Marker({
        position: new this.AMap.LngLat(fixed.lng, fixed.lat),
        content: pin.content, anchor: "center", zIndex: pin.zIndex,
      });
      marker.setMap(this.map);
      this.markers.set(pin.key, marker);
    }
    if (this.options.showAnchor === false) {
      this.map.setZoomAndCenter(11, [anchor.lng, anchor.lat]);
    } else {
      this.map.setFitView();
    }
  }

  /** 切换"只看市中心"与"显示全部"。 */
  setView(showAll) {
    this.options = { ...this.options, showAll: Boolean(showAll), showAnchor: !showAll };
    if (this.pois) this.render(this.pois, this.anchor);
  }

  destroy() {
    if (this.map) this.map.destroy();
    this.map = null;
    this.markers.clear();
    this.ready = false;
  }
}

/* ---------------------------------------------------------------- Leaflet 底图（免费、无需 key） */

class LeafletPicker {
  constructor(container, config, hooks, options) {
    this.container = container;
    this.config = config;
    this.hooks = hooks;
    this.options = options || { showAll: false, showAnchor: true };
    this.map = null;
    this.markers = new Map();
    this.ready = false;
    this.kind = "leaflet";
  }

  async load() {
    const cdns = this.config.leaflet_cdns && this.config.leaflet_cdns.length
      ? this.config.leaflet_cdns
      : [{ name: "unpkg", js: this.config.leaflet_js, css: this.config.leaflet_css }];
    const problems = [];
    for (const cdn of cdns) {
      try {
        await this.#loadAsset("link", cdn.css, "stylesheet", 8000);
        await this.#loadAsset("script", cdn.js, null, 8000);
        if (!window.L) throw new Error("脚本已加载但未挂载 window.L");
        this.L = window.L;
        this.loadedFrom = cdn.name;
        return true;
      } catch (error) {
        problems.push(`${cdn.name}: ${error.message}`);
      }
    }
    this.loadError = problems.join("；");
    return false;
  }

  /** 加载外部资源；带超时，避免某个 CDN 挂起导致一直转圈。 */
  #loadAsset(tag, url, rel, timeoutMs) {
    return new Promise((resolve, reject) => {
      const node = document.createElement(tag);
      if (tag === "link") { node.rel = rel; node.href = url; } else { node.src = url; }
      const timer = setTimeout(() => {
        reject(new Error("加载超时"));
      }, timeoutMs || 8000);
      const done = (fn) => (event) => { clearTimeout(timer); fn(event); };
      node.onload = done(resolve);
      node.onerror = done(() => reject(new Error("加载失败（网络或 CSP 拦截）")));
      document.head.append(node);
    });
  }

  build(pois, anchor) {
    // 可能在「示意地图」之后重新挂载：先清掉上一轮残留的示意内容与旧实例。
    if (this.map) { try { this.map.remove(); } catch (_) { /* 忽略 */ } this.map = null; }
    if (!this.container.classList.contains("map-live")) this.container.replaceChildren();
    this.map = this.L.map(this.container, { zoomControl: true, attributionControl: true }).setView([anchor.lat, anchor.lng], 12);
    this.#addTiles(this.config.tile_url, this.config.tile_subdomains, this.config.tile_attribution, this.config.tile_crs);
    this.#bindPicking();
    this.ready = true;
    this.container.classList.add("map-live");
    this.render(pois, anchor);
  }

  /** 点选模式：高德瓦片是 GCJ-02 要反解；OSM 备用瓦片本身就是 WGS84，直接用。 */
  #bindPicking() {
    if (!this.map || typeof this.map.on !== "function") return;
    this.map.on("click", (event) => {
      const hooks = this.hooks || {};
      if (!hooks.onPickCoordinate || !hooks.isPicking || !hooks.isPicking()) return;
      if (!event || !event.latlng) return;
      const raw = { lat: event.latlng.lat, lng: event.latlng.lng };
      hooks.onPickCoordinate(this.tileCrs === "gcj02" ? wgs84FromGcj02(raw) : raw);
    });
  }

  /** 加瓦片层；若头几块全失败，自动切到备用瓦片源（高德瓦片不通时用 OSM）。 */
  #addTiles(url, subdomains, attribution, crs) {
    this.tileErrors = 0;
    this.tileLoaded = 0;
    this.tileCrs = crs || "gcj02";
    const layer = this.L.tileLayer(url, {
      maxZoom: 18,
      attribution: attribution || "",
      subdomains: subdomains || "1234",
    });
    layer.on("load", () => { this.tileLoaded += 1; });
    layer.on("tileerror", () => {
      this.tileErrors += 1;
      if (this.tileLoaded === 0 && this.tileErrors === 3 && !this.fallbackTried) {
        this.fallbackTried = true;
        const fallback = this.config.fallback_tile;
        if (fallback) {
          this.map.removeLayer(layer);
          this.#addTiles(fallback.url, "", fallback.attribution, fallback.crs || "wgs84");
          if (this.onTilesFallback) this.onTilesFallback(fallback.name);
        }
      }
    });
    layer.addTo(this.map);
    return layer;
  }

  render(pois, anchor) {
    if (!this.ready) return;
    this.pois = pois;
    this.anchor = anchor;
    const trip = this.hooks.getTrip();
    const pins = collectPins(pois, anchor, trip, this.hooks.getCurrentDay(),
      this.hooks.getSelectedPoi(), this.hooks.onSelectPoi, this.options);
    for (const marker of this.markers.values()) marker.remove();
    this.markers.clear();
    const project = (point) => (this.tileCrs === "gcj02" ? gcj02FromWgs84(point) : point);
    for (const pin of pins) {
      const fixed = project(pin.point);
      const marker = this.L.marker([fixed.lat, fixed.lng], {
        icon: this.L.divIcon({
          html: pin.content.outerHTML, className: "leaflet-pin-wrap",
          iconSize: [28, 28], iconAnchor: [14, 14],
        }),
        zIndexOffset: pin.zIndex,
      }).addTo(this.map);
      marker.on("click", () => {
        if (pin.key === "__anchor__") return;
        this.hooks.onSelectPoi(pin.key);
      });
      this.markers.set(pin.key, marker);
    }
    const points = pins.map((pin) => { const fixed = project(pin.point); return [fixed.lat, fixed.lng]; });
    if (!points.length) return;
    if (this.options.showAnchor === false) {
      // 全览：远郊点也被框进来，视野会缩小到市中心糊成一团的级别——这是刻意的，用于看整体跨度
      this.map.fitBounds(points, { padding: [30, 30] });
    } else {
      this.map.fitBounds(points, { padding: [40, 40], maxZoom: 14 });
    }
  }

  /** 切换"只看市中心"与"显示全部"。 */
  setView(showAll) {
    this.options = { ...this.options, showAll: Boolean(showAll), showAnchor: !showAll };
    if (this.pois) this.render(this.pois, this.anchor);
  }

  destroy() {
    if (this.map) this.map.remove();
    this.map = null;
    this.markers.clear();
    this.ready = false;
    this.container.classList.remove("map-live");
  }
}

/* ---------------------------------------------------------------- 工厂 */

/** 按 config.provider 选择实现；未配置时返回 null（调用方走示意地图）。 */
function createPicker(container, config, hooks, options) {
  if (!config || !config.ready) return null;
  if (config.provider === "leaflet") return new LeafletPicker(container, config, hooks, options);
  if (config.provider === "amap") return new AMapPicker(container, config, hooks, options);
  return null;
}

window.IRMap = {
  PIN_STATE, PIN_LABEL, poiPinState, poiDayBadge, gcj02FromWgs84, wgs84FromGcj02,
  approxKm, densestCluster, anchorOffset,
  collectPins, createPicker, AMapPicker, LeafletPicker,
  MapPicker: AMapPicker,   // 兼容旧名
  build: "map.js/2026-09-v3",
};
console.info("[IRMap] build", window.IRMap.build);
