"use strict";
/* 行程概览、当前日选择、停靠点预检与编辑；依赖 runtime、flow、day_cards。 */

/* ---------------------------------------------------------------- 行程概览渲染 */

function renderTrip() {
  const trip = state.trip;
  if (typeof renderRecommendations === 'function') renderRecommendations();
  if (typeof renderBudgetAssessment === 'function') renderBudgetAssessment();
  const panel = $("trip-panel");
  updateSetupDisclosure(trip);
  if (!trip) { panel.hidden = true; return; }
  panel.hidden = false;

  const profile = trip.user_profile;
  const meta = $("trip-meta");
  meta.replaceChildren();
  const party = {solo:"独自出行",couple:"双人出行",family_kids:"带小孩",senior:"长者同行"};
  const pacing = {relaxed:"轻松",balanced:"均衡",packed:"紧凑"};
  const facts = [
    ["日期", `${trip.days[0]?.date || "—"} 起 · ${trip.days.length} 天`],
    ["住宿", trip.anchor_hotel?.name_zh || "已选择住宿"],
    ["同行", party[profile.party_composition] || profile.party_composition],
    ["节奏", pacing[profile.pacing] || profile.pacing],
    ["每人预算", trip.budget == null ? '未设置' : `¥${(trip.budget.amount_cents / 100).toLocaleString('zh-CN', {minimumFractionDigits:2,maximumFractionDigits:2})} / 人（整趟）`],
  ];
  for (const [label, value] of facts) {
    const row = element("div", "fact");
    const display = element('strong', '', value);
    if (label === '住宿' && trip.anchor_hotel?.name_zh) {
      display.setAttribute('data-i18n-ignore','');
      if(typeof placeNameNode==='function') placeNameNode(display,{...trip.anchor_hotel,type:'hotel'});
    }
    row.append(element("span", "", label), display);
    meta.append(row);
  }

  const container = $("days");
  container.replaceChildren();

  // 当前浏览天：切换后地图上的图钉状态会随之变化
  const tabs = element("div", "day-tabs");
  for (const day of trip.days) {
    const tab = element("button", "day-tab", `Day ${day.day_index}`);
    tab.dataset.dayTab = String(day.day_index);
    tab.setAttribute("aria-pressed", String(day.day_index === state.currentDayIndex));
    if (day.day_index === state.currentDayIndex) tab.classList.add("selected");
    tab.addEventListener("click", () => setCurrentDay(day.day_index));
    tabs.append(tab);
  }
  container.append(tabs);

  renderDayCards(trip, container);
  if(typeof refreshPlaceNames==='function') void refreshPlaceNames();
}

function dayStatusLabel(day) {
  const used = day.ordered_stops.filter(s=>(s.stop_type || 'poi')==='poi').length;
  const cap = day.poi_cap;
  if (day.day_status === "locked") return "全部已固定";
  if (day.day_status === "arrival_only") return "抵达日";
  if (day.day_status === "empty") return "未装载";
  // poi_cap 只是按节奏给出的建议值：后端 _cap_warning 只回 pacing_warning，从不阻止加入。
  // 所以这里不能写「上限 / 已满」，否则会被读成硬限制（语义与文案必须一致）。
  if (cap && used > cap) return `已超建议 ${used}/${cap}`;
  if (day.day_status === "fulfilled") return `已达建议 ${used}/${cap}`;
  return `建议 ${used}/${cap}`;
}

/** 切换当前浏览天并刷新图钉状态。 */
function setCurrentDay(dayIndex) {
  state.currentDayIndex = dayIndex;
  for (const node of document.querySelectorAll("[data-day-tab]")) {
    const active = Number(node.dataset.dayTab) === dayIndex;
    node.classList.toggle("selected", active);
    node.setAttribute("aria-pressed", String(active));
  }
  redrawMap();
}

/* ---------------------------------------------------------------- 加入行程前的规则预检
 * 以前硬冲突要等景点「已经加进行程」之后才提示，用户只能事后二选一（保留 / 移除）。
 * 现在点「加入行程」会先预检：有硬冲突就先说清，需要再点一次才真的加入。
 */

/** 已确认过一次的预检结论：{key, check}。换一天或换 POI 就失效。 */
let pendingConflict = null;

function resetAddConfirmation() {
  pendingConflict = null;
  if ($("d-add")) $("d-add").textContent = "加入行程";
}

/** 预检候选点。返回 null 表示规则引擎不可用 —— 这种情况不能阻断加入（属降级）。 */
async function precheckStop(dayIndex, poiId) {
  if (typeof engineReady === "function" && !engineReady("rules_engine")) return null;
  try {
    return await api(`/api/trips/${state.trip.trip_id}/rules:precheck`,
      { method: "POST", body: { day_index: dayIndex, poi_id: poiId } });
  } catch (error) {
    return null;
  }
}

async function addSelectedToDay() {
  if (!state.trip || !state.selected) return;
  const dayIndex = Number($("d-day").value);
  const poiId = state.selected.poi_id;
  try {
    // 第一次点击：先预检。有硬冲突只提示，不动行程。
    const key = `${dayIndex}:${poiId}`;
    if (!pendingConflict || pendingConflict.key !== key) {
      const check = await precheckStop(dayIndex, poiId);
      if (check && check.would_block) {
        pendingConflict = { key, check };
        const detail = check.hard_conflicts
          .map((notice) => (typeof noticeText === "function" ? noticeText(notice) : notice.message_key))
          .join("；");
        $("d-hint").textContent = `预检发现硬冲突：${detail}。再次点击「加入行程」表示仍然保留。`;
        $("d-add").textContent = "确认仍然加入";
        notify(`预检发现 ${check.hard_conflicts.length} 条硬冲突，已在抽屉里说明`, true);
        return;
      }
    }
    const data = await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops`,
      { method: "POST", body: { poi_id: poiId } });
    state.trip = data.trip;
    state.currentDayIndex = dayIndex;
    resetAddConfirmation();
    $("detail").close();
    const warning = data.pacing_warning;
    // 超建议上限不是失败：点位已经写进去了，用普通提示而不是报错样式，避免读成「被拒绝」。
    notify(warning ? `已加入 Day ${dayIndex}；${warning}（仅提示，可继续添加）` : `已加入 Day ${dayIndex}`);
    // 规则参与添加流程：加完立刻求值，硬冲突（如周一闭馆）在 ④ 面板给出「保留 / 移除」。
    await afterTripEditSafely("add_stop");
  } catch (error) {
    notify(error.message, true);
  }
}

/** 编辑后统一收口：清掉失效的路线/离线结果 → 重渲染 → 重新求值规则。
 *
 *  求值失败只降级提示，不能把「已成功写入的编辑」报成失败。
 */
async function afterTripEditSafely(trigger) {
  if (typeof afterTripEdit === "function") {
    try {
      await afterTripEdit(trigger);
      return;
    } catch (error) {
      notify(`行程已更新，但规则未完成校验：${error.message}`, true);
      return;
    }
  }
  renderTrip();
  redrawMap();
  renderPoiList();
}

async function removeStop(dayIndex, poiId) {
  if (!state.trip) return;
  try {
    const data = await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops/${poiId}`,
      { method: "DELETE" });
    state.trip = data.trip;
    notify("已移除");
    await afterTripEditSafely("remove_stop");
  } catch (error) {
    notify(error.message, true);
  }
}
