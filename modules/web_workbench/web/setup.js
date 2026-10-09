"use strict";
/* 设定表单、保存/预校验/回滚、默认值与草稿；依赖 runtime、anchors、flow。 */

function readBudget() {
  const value = ($('budget-per-person')?.value || '').trim();
  if (typeof readCurrencyBudget === 'function') return readCurrencyBudget(value);
  if (!value) return null;
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) throw new Error('每人预算须为非负金额，最多两位小数');
  const [yuan, fraction = ''] = value.split('.');
  const cents = Number(yuan) * 100 + Number(fraction.padEnd(2, '0'));
  if (!Number.isSafeInteger(cents) || cents > 999999999999) throw new Error('每人预算超出允许范围');
  return {scope:'per_person',currency:'CNY',amount_cents:cents};
}

function readSetup() {
  const interests = Array.from(document.querySelectorAll('input[name="interest"]:checked'))
    .map((node) => node.value);
  const hub = anchorById("hubs", $("arrival-hub").value);
  if (!hub) throw new Error("请先选择抵达口岸（可用中文 / 英文 / 拼音搜索）");
  const hotel = readHotelAnchor();
  const arrivalLocal = `${$("arrival-date").value}T${$("arrival-time").value}:00+08:00`;
  const arrivalAt = Math.floor(new Date(arrivalLocal).getTime() / 1000);
  return {
    user_profile: {
      party_composition: $("party").value,
      pacing: $("pacing").value,
      interests,
      walking_speed_factor: 1.0,
    },
    duration_days: Number($("duration-days").value),
    budget: readBudget(),
    start_date: $("arrival-date").value,
    ...(state.trip ? {} : {daily_start_local: "09:00"}),
    anchor_arrival: {
      at: arrivalAt, location_name: `${hub.name_zh} / ${hub.name_en}`,
      coordinate: { lat: hub.lat, lng: hub.lng, crs: "WGS84" },
    },
    anchor_hotel: hotel,
    // 契约 anchor_departure（可空）：以前前端完全没有入口，导致最后一段无法推演。
    anchor_departure: readDeparture(),
  };
}

/** 离境默认值：抵达当天 +（天数 - 1），即行程最后一天；时刻默认 12:00。 */
function departureDefaults() {
  const arrival = $("arrival-date").value || defaultArrival().date;
  const duration = Number($("duration-days").value) || 1;
  const date = new Date(`${arrival}T00:00:00+08:00`);
  date.setDate(date.getDate() + Math.max(0, duration - 1));
  const pad = (value) => String(value).padStart(2, "0");
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: "12:00",
  };
}

/** 用户没手动改过离境日期/时刻时，让它跟着抵达日期与天数走。 */
function syncDepartureDefaults(force = false) {
  if (!$("departure-date")) return;
  const { date, time } = departureDefaults();
  if (force || !state.departureTouched) {
    $("departure-date").value = date;
    $("departure-time").value = time;
  }
}

/** 读取离境锚点（可选）。勾了却填不全就明确报错，绝不静默丢掉这一段。 */
function readDeparture() {
  if (!$("has-departure") || !$("has-departure").checked) return null;
  const hub = anchorById("hubs", $("departure-hub").value);
  if (!hub) throw new Error("已勾选离境安排，请选择离境口岸（可用中文 / 英文 / 拼音搜索）");
  const date = $("departure-date").value, time = $("departure-time").value;
  if (!date || !time) throw new Error("已勾选离境安排，请填写离境日期与时刻");
  const at = Math.floor(new Date(`${date}T${time}:00+08:00`).getTime() / 1000);
  if (Number.isNaN(at)) throw new Error("离境日期与时刻无法解析，请检查后重试");
  return {
    at,
    location_name: `${hub.name_zh} / ${hub.name_en}`,
    coordinate: { lat: hub.lat, lng: hub.lng, crs: "WGS84" },
    // 契约默认 true；国内段可由用户取消勾选。
    is_international: Boolean($("departure-international") && $("departure-international").checked),
  };
}

/* ---------------------------------------------------------------- 创建后修改设定
 * 以前创建完就改不了出行构成 / 节奏 / 兴趣 / 日期 / 每日出发时刻，只能重新建一份行程。
 * 这里让 ① 复用同一套表单：载入当前行程的设定，提交时走 PATCH 更新而不是新建。
 */

/** 把一份行程的设定回填到 ① 表单。 */
function formFromTrip(trip) {
  const set = (id, value) => { if ($(id) && value !== undefined && value !== null) $(id).value = String(value); };
  const arrival = trip.anchor_arrival || {};
  set("duration-days", (trip.days || []).length);
  set("party", trip.user_profile.party_composition);
  set("pacing", trip.user_profile.pacing);
  if (typeof setCurrencyBudgetInput === 'function') setCurrencyBudgetInput(trip.budget?.amount_cents ?? null);
  else if ($('budget-per-person')) $('budget-per-person').value = trip.budget == null ? '' : (trip.budget.amount_cents / 100).toFixed(2);
  const wanted = new Set(trip.user_profile.interests || []);
  for (const node of document.querySelectorAll('input[name="interest"]')) {
    if (node && typeof node === "object") node.checked = wanted.has(node.value);
  }
  set("arrival-date", ymd(arrival.at));
  set("arrival-time", hhmm(arrival.at));
  // 关键词先清空：否则上次搜过的词会把下拉过滤掉，导致下面赋不进值。
  set("hub-search", "");
  set("hotel-search", "");
  renderAnchorPickers();
  const hub = anchorNear("hubs", arrival.coordinate);
  if (hub) $("arrival-hub").value = hub.id;
  const hotel = storeSavedHotel(trip.anchor_hotel);
  state.pickedHotel = null;
  renderAnchorPickers();
  if ($('hotel')) $('hotel').value = hotel?.id || '';

  const departure = trip.anchor_departure;
  if ($("has-departure")) {
    $("has-departure").checked = Boolean(departure);
    $("departure-fields").hidden = !departure;
    state.departureTouched = Boolean(departure);
    if (departure) {
      const depHub = anchorNear("hubs", departure.coordinate);
      const first = anchors("hubs")[0];
      if (depHub || first) $("departure-hub").value = (depHub || first).id;
      set("departure-date", ymd(departure.at));
      set("departure-time", hhmm(departure.at));
      if ($("departure-international")) {
        $("departure-international").checked = departure.is_international !== false;
      }
    }
  }
  renderAnchorPickers();
  $("anchor-pick-state").textContent = pickStateText();
  state.setupBaseline = setupSettingsIdentity();
  if (typeof renderRecommendations === "function") renderRecommendations();
}

function resetSetup() {
  discardDraft();
  if (state.trip) { formFromTrip(state.trip); return; }
  $("setup-form").reset();
  if (typeof setCurrencyBudgetInput === 'function') setCurrencyBudgetInput(null);
  if (typeof currencyControls === 'function') currencyControls();
  state.pickedHotel = null;
  state.savedHotels = [];
  state.departureTouched = false;
  $("departure-fields").hidden = true;
  applyArrivalDefaults();
  renderAnchorPickers();
  $("anchor-pick-state").textContent = pickStateText();

  if (typeof renderRecommendations === "function") renderRecommendations();
}

/** 用 ① 的当前内容更新已有行程的设定（不新建行程）。 */
async function saveSettings(payload) {
  const budgetOnly = state.setupBaseline === setupSettingsIdentity()
    && JSON.stringify(payload.budget) !== JSON.stringify(state.trip.budget ?? null);
  state.busy = true;
  try {
    state.trip = await api(`/api/trips/${encodeURIComponent(state.trip.trip_id)}`,
      { method: "PATCH", version: state.trip.version, body: budgetOnly ? {budget:payload.budget} : payload });
    if (budgetOnly) flow.offline = null;
    else resetFlowResults();
    state.setupBaseline = setupSettingsIdentity();
    discardDraft();
    notify(`设定已更新：${tripDisplayName(state.trip)}`);
    if (typeof rememberTrip === "function") rememberTrip();
    renderTrip();
    await refreshHistorySafely();
    if (budgetOnly) renderFlow();
    else if (typeof afterTripEditSafely === "function") await afterTripEditSafely("change_config");
  } catch (error) {
    notify(error.message, true);
  } finally {
    state.busy = false;
  }
}

async function createTrip(event) {
  event.preventDefault();
  if (state.busy) return;
  // Arrow buttons move by 100 yuan; manually entered amounts may include cents.
  const budgetInput = $('budget-per-person');
  const setupForm = $('setup-form');
  budgetInput.step = 'any';
  let valid = true;
  try {
    if (typeof setupForm.reportValidity === 'function') valid = setupForm.reportValidity();
  } finally {
    budgetInput.step = '100';
  }
  if (!valid) return;
  let payload;
  try {
    payload = readSetup();
  } catch (error) {
    notify(error.message, true);
    return;
  }
  if (!Number.isInteger(payload.duration_days) || payload.duration_days < 1 || payload.duration_days > 15) {
    notify("行程天数必须是 1~15 的整数", true);
    return;
  }
  // 编辑模式：更新已有行程的设定，不新建。
  if (state.trip) {
    await saveSettings(payload);
    return;
  }
  if (Number.isNaN(payload.anchor_arrival.at)) {
    notify("抵达时间无法解析，请检查日期与时刻", true);
    return;
  }
  state.busy = true;
  try {
    // 先预校验、再落盘：非法输入在这里就被挡住，不会留下「建了一半」的行程。
    // （原来是一提交就直接 POST /api/trips，非法输入或后续规则拒绝时行程已经存下来了。）
    await api("/api/trips:validate", { method: "POST", body: payload });
    state.trip = await api("/api/trips", { method: "POST", body: payload });
    state.setupBaseline = setupSettingsIdentity();
    state.currentDayIndex = 1;
    resetFlowResults();
    discardDraft();                    // 创建成功，草稿使命结束
    notify(`行程已创建：${tripDisplayName(state.trip)}`);
    if (typeof rememberTrip === "function") rememberTrip();
    renderTrip();
    await refreshHistorySafely();
    if (typeof evaluateTrip === "function") {
      try {
        // 规则要参与整个流程：创建完成即求值一次，缺数据时在 ④ 面板显式说明。
        // trigger 必须取自契约 rules.json#/execution_model/trigger_events（8 个事件，没有 create_trip）。
        // 刚创建、尚未发生任何改单动作，语义上正确的取值是 load_trip；传非法值会被规则引擎 400 拒绝，
        // 表现为「行程已创建，但规则未完成校验」。
        await evaluateTrip("load_trip");
      } catch (error) {
        // 契约拒绝（4xx）= 这份行程与规则契约不一致 → 回滚，别留下校验不过的半成品。
        // 引擎不可达（5xx / 网络）= 降级，行程本身没问题，保留并提示重新校验。
        if (error.status >= 400 && error.status < 500) {
          await rollbackTripCreation(state.trip.trip_id);
          notify(`行程创建后规则校验被拒绝，已回滚：${error.message}`, true);
          return;
        }
        notify(`行程已创建，但规则未完成校验：${error.message}`, true);
      }
    }
  } catch (error) {
    notify(error.message, true);
  } finally {
    state.busy = false;
  }
}

/** 回滚一次创建：规则契约拒绝时删掉刚建的那份，避免留下半成品行程。 */
async function rollbackTripCreation(tripId) {
  try {
    await api(`/api/trips/${encodeURIComponent(tripId)}`, { method: "DELETE" });
  } catch (error) {
    notify(`自动回滚失败，请手动删除行程 ${tripId}：${error.message}`, true);
  }
  state.trip = null;
  resetFlowResults();
  renderTrip();
  if (typeof renderFlow === "function") renderFlow();
  await refreshHistorySafely();
}

/** 行程整体换掉后清空上一份的路线/离线结果（flow.js 未加载时为空操作）。 */
function resetFlowResults() {
  if (typeof flow !== "undefined" && flow) {
    flow.evaluations = {};
    flow.routes = {};
    flow.offline = null;
  }
}

/** 刷新历史下拉框；失败不打断主流程。 */
async function refreshHistorySafely() {
  if (typeof refreshHistory !== "function") return;
  try {
    await refreshHistory();
  } catch (error) {
    console.warn("[workbench] 历史行程列表刷新失败", error);
  }
}

/* ---------------------------------------------------------------- 启动 */

/** 当前北京时间（不依赖运行机器的本地时区）。 */
function shanghaiNow() {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Shanghai" }));
}

/** 抵达日期/时刻的默认值：按当前北京时间向上取整到下一个 30 分钟。
 *
 *  以前这两个值写死在 HTML 里（2026-10-12 23:30）：一旦过期，每个新用户都要从
 *  一个不合理且已经过去的日期开始手改两个字段。这里动态给默认值，用户改过之后不再覆盖。
 */
function defaultArrival() {
  const now = shanghaiNow();
  now.setSeconds(0, 0);
  const minutes = now.getMinutes();
  if (minutes > 0 && minutes <= 30) now.setMinutes(30);
  else if (minutes > 30) { now.setHours(now.getHours() + 1); now.setMinutes(0); }
  const pad = (value) => String(value).padStart(2, "0");
  return {
    date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
  };
}

/** 把动态默认值写进表单（页面初始化与「重置」都走这里）。
 *
 *  草稿存在时不覆盖：草稿恢复要在 boot 里晚于本函数执行，见 restoreDraft()。
 */
function applyArrivalDefaults() {
  const { date, time } = defaultArrival();
  $("arrival-date").value = date;
  $("arrival-time").value = time;
}

/** 离境 / 返程区块：可选、默认折叠。元素缺失时跳过，保证裁剪过的 DOM 仍能用。 */
function wireDeparture() {
  if (!$("has-departure")) return;
  $("has-departure").addEventListener("change", () => {
    const on = $("has-departure").checked;
    $("departure-fields").hidden = !on;
    if (on) syncDepartureDefaults(true);
    else state.departureTouched = false;
  });
  $("departure-hub-search").addEventListener("input", () => renderAnchorPickers());
  for (const id of ["departure-date", "departure-time"]) {
    $(id).addEventListener("input", () => { state.departureTouched = true; });
  }
  // 抵达日期与天数决定「最后一天」是哪天，离境默认值跟着走（用户手动改过就不动）。
  $("arrival-date").addEventListener("input", () => syncDepartureDefaults());
  $("duration-days").addEventListener("input", () => syncDepartureDefaults());
}

/* ---------------------------------------------------------------- ① 的草稿
 * 以前没有草稿：刷新或误关页面时，① 里没提交的设定全部丢失，只能重填。
 * 这里把整份表单快照放进 localStorage（不是把行程存起来 —— 那时还没有行程）。
 * 创建成功后草稿作废，避免下次打开又冒出一份过期的旧设定。
 */
const DRAFT_KEY = "inboundroute.setupDraft";

function formSnapshot() {
  const box = (id) => $(id) || null;
  return {
    trip_id: state.trip?.trip_id || null,
    duration_days: box("duration-days") ? box("duration-days").value : "",
    party: box("party") ? box("party").value : "",
    pacing: box("pacing") ? box("pacing").value : "",
    budget_per_person: box('budget-per-person')?.value || '',
    ...(typeof currencySnapshot === 'function' ? {currency_settings:currencySnapshot()} : {}),
    interests: Array.from(document.querySelectorAll('input[name="interest"]'))
      .filter((node) => node.checked).map((node) => node.value),
    arrival_date: box("arrival-date") ? box("arrival-date").value : "",
    arrival_time: box("arrival-time") ? box("arrival-time").value : "",
    arrival_hub: box("arrival-hub") ? box("arrival-hub").value : "",
    hub_search: box("hub-search") ? box("hub-search").value : "",
    hotel: box("hotel") ? box("hotel").value : "",
    hotel_search: box("hotel-search") ? box("hotel-search").value : "",
    saved_hotels: (state.savedHotels || []).map(hotel => readSavedHotelSnapshot(hotel)),
    has_departure: box("has-departure") ? box("has-departure").checked : false,
    departure_hub: box("departure-hub") ? box("departure-hub").value : "",
    departure_date: box("departure-date") ? box("departure-date").value : "",
    departure_time: box("departure-time") ? box("departure-time").value : "",
    departure_international: box("departure-international")
      ? box("departure-international").checked : true,
  };
}

function saveDraft() {
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(formSnapshot())); }
  catch (_) { /* 隐私模式下写不了 localStorage：不影响主流程 */ }
}

function setupSettingsIdentity() {
  const {budget_per_person, currency_settings, ...settings} = formSnapshot();
  return JSON.stringify(settings);
}

function discardDraft() {
  try { localStorage.removeItem(DRAFT_KEY); } catch (_) { /* 同上 */ }
}

function loadDraft() {
  try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); }
  catch (_) { return null; }
}

function readSavedHotelSnapshot(hotel) {
  return {name_zh:hotel.name_zh,name_en:hotel.name_en,
    ...(hotel.name_pinyin ? {name_pinyin:hotel.name_pinyin} : {}),coordinate:hotelCoordinate(hotel),poi_id:hotel.poi_id || null};
}

/** 把草稿写回表单。必须先 renderAnchorPickers() 建好选项，否则 select.value 赋不进去。 */
function applyDraft(draft) {
  if (!draft || typeof draft !== "object") return false;
  const set = (id, value) => { if ($(id) && value !== undefined && value !== null) $(id).value = String(value); };
  for (const hotel of draft.saved_hotels || []) storeSavedHotel(hotel);
  let legacyHotel = null;
  if (draft.picked_hotel) {
    const candidate = anchorById('hotels', draft.hotel);
    const name = (draft.hotel_name || '').trim();
    if (draft.hotel_mode === 'manual' && name) legacyHotel = storeSavedHotel({name_zh:name,name_en:name,coordinate:draft.picked_hotel});
    else if (candidate) legacyHotel = storeSavedHotel({...readSavedHotelSnapshot(candidate),coordinate:draft.picked_hotel});
  }
  set('hotel-search','');
  renderAnchorPickers();                       // 先建选项，再赋 value
  set("duration-days", draft.duration_days);
  set("party", draft.party);
  set("pacing", draft.pacing);
  if (typeof applyCurrencySnapshot === 'function') applyCurrencySnapshot(draft.currency_settings || {code:'CNY',rate:'1',source:'CNY'});
  if ($('budget-per-person')) $('budget-per-person').value = draft.budget_per_person ?? '';
  const wanted = new Set(draft.interests || []);
  for (const node of document.querySelectorAll('input[name="interest"]')) {
    if (node && typeof node === "object") node.checked = wanted.has(node.value);
  }
  set("arrival-date", draft.arrival_date);
  set("arrival-time", draft.arrival_time);
  set("arrival-hub", draft.arrival_hub);
  set("hotel", legacyHotel?.id || (draft.hotel_mode === 'manual' || draft.picked_hotel ? '' : draft.hotel || ''));
  // 关键词最后回填：它只影响过滤，回填后再渲染一次即可保留已选中的项。
  set("hub-search", draft.hub_search);
  set("hotel-search", legacyHotel ? "" : draft.hotel_search || "");
  state.pickedHotel = null;
  if ($("has-departure")) {
    $("has-departure").checked = Boolean(draft.has_departure);
    if ($("departure-fields")) $("departure-fields").hidden = !draft.has_departure;
    if (draft.has_departure) {
      set("departure-hub", draft.departure_hub);
      set("departure-date", draft.departure_date);
      set("departure-time", draft.departure_time);
      if ($("departure-international")) {
        $("departure-international").checked = draft.departure_international !== false;
      }
      state.departureTouched = true;              // 草稿里的离境值优先，别再被默认值覆盖
    }
  }
  renderAnchorPickers();
  if ($("anchor-pick-state")) $("anchor-pick-state").textContent = pickStateText();
  if (typeof renderRecommendations === "function") renderRecommendations();
  return true;
}
