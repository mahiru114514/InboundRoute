"use strict";
/* 口岸与住宿的本地搜索及已保存住宿；依赖 runtime。 */

/* ---------------------------------------------------------------- 设定表单 */

/** 拉取抵达 / 离境口岸与住宿候选（trip_engine 的 GET /anchors）。
 *
 *  失败必须显式暴露：以前清单写死在前端，trip_engine 没起来时下拉框照样有内容，
 *  用户填完点「创建行程」才失败。现在清单取不到就禁用下拉并说明原因。
 */
async function loadAnchors() {
  const data = await api("/api/anchors");
  state.anchors = { hubs: data.hubs || [], hotels: data.hotels || [] };
  renderAnchorPickers();
}

async function loadPois() {
  const data = await api("/api/pois");
  state.pois = data.pois || [];
  renderAnchorPickers();
  renderPoiList();
  renderSketchMap();
}

/** 抵达 / 离境口岸与住宿候选清单：由 trip_engine 的 GET /anchors 供给。
 *
 *  以前这两份清单（各 6 条）是写死在这个文件里的，后果是「加一个口岸必须改前端代码」，
 *  而且浏览器缓存旧 JS 时会继续用旧清单。现在主数据在 trip_engine/anchors_seed.py。
 *
 *  这里刻意**不再**留一份内置兜底清单：创建行程本来就必须能连上 trip_engine，
 *  没有它连 POST /api/trips 都发不出去，留一份写死的口岸只会掩盖「引擎没起来」这个真问题。
 *  取不到清单时下拉框会禁用并写明原因（见 renderAnchorSelect）。
 *
 *  坐标约定：契约（trip.schema.json#/anchor_hotel）允许 name_pinyin，所以中文 / 英文 /
 *  拼音都能联想检索；坐标必须是真正的 WGS84，coordinate_source 如实标注来源：
 *    · curated      —— 人工整理，暂未在真实底图上实测
 *    · approximate  —— 近似值，需核对酒店资料中的位置后再用于规划
 */
function anchors(kind) {
  const local = (state.anchors && state.anchors[kind]) || [];
  return kind === 'hotels' ? [...local, ...(state.savedHotels || [])] : local;
}

/** 联想匹配：中文名 / 英文名 / 拼音（含去空格连写）/ 别名，全部小写包含匹配。 */
function anchorMatches(anchor, keyword) {
  if (!keyword) return true;
  const pinyin = anchor.name_pinyin || "";
  const haystack = [anchor.name_zh, anchor.name_en, pinyin, pinyin.replace(/\s+/g, ""),
    ...(anchor.aliases || [])].join(" ").toLowerCase();
  return haystack.includes(keyword);
}

function anchorById(kind, id) {
  return anchors(kind).find((item) => item.id === id) || null;
}

/** 按关键词重建下拉框；无匹配时禁用并给出提示，绝不静默回退到任意一项。 */
function renderAnchorSelect(kind, selectId, searchId) {
  const all = anchors(kind);
  const keyword = ($(searchId).value || "").trim().toLowerCase();
  const matched = all.filter((anchor) => anchorMatches(anchor, keyword));
  const select = $(selectId);
  const previous = select.value;
  select.replaceChildren();
  if (!matched.length) {
    // 「清单没载入」和「关键词没匹配」是两件事，必须说不同的话：
    // 前者是 trip_engine 没起来，后者才是用户该换关键词。
    const empty = element("option", "", all.length
      ? "没有匹配的口岸/酒店，请换关键词"
      : "清单未载入：trip_engine 未就绪，创建行程前需先启动该模块");
    empty.value = "";
    select.append(empty);
    select.disabled = true;
    select.value = "";            // 显式清空：不给任何默认项，避免拿上一次的选择去建行程
    select.dataset.matches = "0";
    return matched;
  }
  for (const anchor of matched) {
    const option = element("option", "", `${anchor.name_zh} / ${anchor.name_en}`);
    option.setAttribute('data-i18n-ignore','');
    option.value = anchor.id;
    option.title = `${anchor.coordinate_source === "approximate" ? "近似坐标" : "人工整理坐标"} `
      + `${anchor.lat}, ${anchor.lng}（WGS84）`;
    select.append(option);
  }
  select.disabled = false;
  select.dataset.matches = String(matched.length);
  select.value = matched.some((anchor) => anchor.id === previous) ? previous : kind === 'hotels' ? '' : matched[0].id;
  if (kind === 'hotels' && !select.value) {
    const prompt = element('option', '', '请选择住宿');
    prompt.value = '';
    select.append(prompt);
    select.value = '';
  }
  return matched;
}

/** 已保存住宿按原名与完整坐标进入同一搜索清单。 */
function storeSavedHotel(anchor) {
  const point = anchor?.coordinate;
  const name = anchor?.name_zh || anchor?.name_en;
  if (!name || !point || point.crs !== 'WGS84' || !Number.isFinite(point.lat) || !Number.isFinite(point.lng)
      || Math.abs(point.lat) > 90 || Math.abs(point.lng) > 180) return null;
  const normalized = {...anchor,name_zh:anchor.name_zh || name,name_en:anchor.name_en || name,coordinate:{...point},poi_id:anchor.poi_id || null};
  const identical = item => item.name_zh === normalized.name_zh && item.name_en === normalized.name_en
    && JSON.stringify(hotelCoordinate(item)) === JSON.stringify(point) && (item.poi_id || null) === normalized.poi_id;
  const existing = anchors('hotels').find(identical);
  if (existing) return existing;
  const id = 'saved-hotel:' + encodeURIComponent(JSON.stringify([normalized.name_zh,normalized.name_en,point,normalized.poi_id]));
  const saved = {...normalized,id,lat:point.lat,lng:point.lng,coordinate_source:'saved'};
  state.savedHotels = [...(state.savedHotels || []),saved];
  return saved;
}

function hotelCoordinate(hotel) {
  return hotel.coordinate ? {...hotel.coordinate} : {lat:hotel.lat,lng:hotel.lng,crs:'WGS84'};
}

function readHotelAnchor() {
  const hotel = anchorById('hotels', $('hotel').value);
  if (!hotel) throw new Error('请先选择住宿（可用中文 / 英文 / 拼音搜索）');
  return {name_zh:hotel.name_zh,name_en:hotel.name_en,
    ...(hotel.name_pinyin ? {name_pinyin:hotel.name_pinyin} : {}),coordinate:hotelCoordinate(hotel),poi_id:hotel.poi_id || null};
}

function pickStateText() {
  const hotel = anchorById('hotels', $('hotel').value);
  return hotel ? '已选择住宿：' + hotel.name_zh : '请先选择住宿';
}

function renderAnchorPickers() {
  renderAnchorSelect('hubs','arrival-hub','hub-search');
  renderAnchorSelect('hotels','hotel','hotel-search');
  if ($('departure-hub')) renderAnchorSelect('hubs','departure-hub','departure-hub-search');
  if ($('anchor-pick-state')) $('anchor-pick-state').textContent = pickStateText();
}

/** 地图保留坐标回调接口；住宿统一由搜索选择，地图点击不修改住宿。 */
function applyPickedHotelCoordinate() { state.pickTarget = null; }

/** 用坐标就近匹配候选（≤300 m 视为同一个）；匹配不到返回 null。 */
function anchorNear(kind, coordinate) {
  if (!coordinate || coordinate.lat === undefined) return null;
  const rad = Math.PI / 180, R = 6371000;
  const meters = (a, b) => {
    const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  };
  let best = null, bestDistance = Infinity;
  for (const item of anchors(kind)) {
    const distance = meters(coordinate, item);
    if (distance < bestDistance) { best = item; bestDistance = distance; }
  }
  return bestDistance <= 300 ? best : null;
}
