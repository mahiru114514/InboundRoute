"use strict";
/* 景点详情字段映射与抽屉；依赖 runtime、poi_content，事件操作由 itinerary 提供。 */

/* ---------------------------------------------------------------- 详情抽屉的字段映射
 * 严格按 contracts/mappings.json#/drawer_field_map 实现：
 * 每一行都要区分「有值 / null / 空数组」，空值时隐藏或显示「待确认」，绝不显示空白或「—」。
 */

/** 运营时间与闭馆：closure_data_status=unknown 时必须显式提示，不能静默隐藏。
 *
 *  照 contracts/mappings.json#/drawer_field_map/opening_closure：
 *    · 逐条渲染 opening_hours 的 open-close
 *    · closure_rules 中 kind=weekly 渲染为 "Closed on {weekday_label_en}"
 *    · opening_hours=[] → 隐藏整行（此时连「待确认」都不显示）
 */
function openingClosureText(rules) {
  const hours = rules.opening_hours || [];
  if (!hours.length) return null;   // 契约：opening_hours=[] 隐藏整行
  const parts = [];
  for (const slot of hours) {
    if (slot.open && slot.close) {
      parts.push(slot.close_next_day ? `${slot.open} – ${slot.close}（次日）` : `${slot.open} – ${slot.close}`);
    }
  }
  for (const rule of rules.closure_rules || []) {
    if (rule.kind === "weekly" && rule.weekday) {
      // 契约要求英文模板 "Closed on {weekday_label_en}"
      parts.push(`Closed on ${WEEKDAYS_EN[rule.weekday - 1]}`);
    } else if (rule.kind === "holiday_exception_open") parts.push("法定假日照常开放");
    else if (rule.kind === "holiday_exception_closed") parts.push("假日期间闭馆");
    else if (rule.kind === "special_period") parts.push(rule.reason_zh || "特定期闭馆");
    else if (rule.kind === "maintenance") parts.push(rule.reason_zh || "修缮闭馆");
  }
  // 数据可信度是独立于「有没有内容」的一维，必须始终显式提示
  if (rules.closure_data_status === "unknown") parts.push("闭馆信息待确认");
  else if (rules.closure_data_status === "unverified") parts.push("闭馆信息待复核");
  return parts.length
    ? { text: parts.join("；"), warn: rules.closure_data_status !== "verified" }
    : null;
}

/** 建议停留：点值/区间两种，缺失时给参考值并标注。
 *
 *  照 drawer_field_map/suggested_dwell：
 *    · point → "{minutes} 分钟"，range → "{min} - {max} Hours"（区间按契约露小时）
 *    · 缺失 → 默认 90 分钟并标注「参考值」
 */
function dwellText(dwell) {
  const missing = !dwell || (dwell.minutes == null && dwell.minutes_min == null && dwell.minutes_max == null);
  if (missing) return { text: "约 90 分钟（参考值）", isDefault: true };
  if (dwell.kind === "range") {
    const min = dwell.minutes_min, max = dwell.minutes_max;
    if (min != null && max != null) return { text: `${hourText(min)} - ${hourText(max)} Hours` };
    if (min != null) return { text: `至少 ${hourText(min)} Hours` };
  }
  if (dwell.minutes != null) return { text: `${dwell.minutes} 分钟` };
  return { text: "约 90 分钟（参考值）", isDefault: true };
}

/** 120 → "2"，90 → "1.5"，100 → "1.7"（去掉多余的 .0）。 */
function hourText(minutes) {
  const hours = minutes / 60;
  return Number.isInteger(hours) ? String(hours) : hours.toFixed(1);
}

function lightUpText(lightUp) {
  if (!lightUp || !lightUp.windows || !lightUp.windows.length) return null;
  // 契约模板 "{start} - {close} ({label})"，正合 label_zh（如「夏季」）
  const windows = lightUp.windows
    .map((w) => `${w.start} - ${w.close}${w.label_zh ? ` (${w.label_zh})` : ""}`)
    .join("；");
  return { text: windows };
}

/** 预约要求：三态。字段缺失→隐藏；false→「无需预约」；true→「需提前 N 天预约」。
 *
 *  `reservation_required` 是可选 boolean；字段缺失表示尚未核对，false 是明确结论，
 *  应当照契约渲染成「无需预约」，而不是当成"没有信息"隐藏掉。
 */
function reservationText(rules) {
  if (rules.reservation_required === true) {
    const days = rules.advance_booking_days;
    return { text: days ? `需提前 ${days} 天预约` : "需预约", warn: !days };
  }
  if (rules.reservation_required === false) return { text: "无需预约" };
  return null;   // 字段缺失 → 隐藏该行
}

/** 生成抽屉的四行（返回 null 表示该行隐藏）。 */
function detailRows(poi) {
  const rules = poi.operating_rules || {};
  const rows = [];
  const opening = openingClosureText(rules);
  if (opening) rows.push({ label: "开放与闭馆", ...opening });
  if (rules.last_entry_time) rows.push({ label: "截止入场", text: `${rules.last_entry_time} Last Entry` });
  const light = lightUpText(rules.light_up);
  if (light) rows.push({ label: "亮灯时段", ...light });
  rows.push({ label: "建议停留", ...dwellText(rules.dwell_time) });
  const reservation = reservationText(rules);
  if (reservation) rows.push({ label: "预约", ...reservation });
  const dropOffs = poi.drop_off_locations || [];
  if (dropOffs.length) {
    rows.push({ label: "落客点", text: dropOffs.map((item) => `${item.desc_zh}（${item.source}）`).join("；") });
  }
  const dataNotes = (poi.tags || []).filter((tag) => /待核实|待复核|资料存在冲突|规划参考|另行预约|另行公告|须查公告|入口：/.test(tag));
  if (dataNotes.length) rows.push({label: "数据说明", text: dataNotes.join("；"), warn: true});
  return rows;
}

/* ---------------------------------------------------------------- 详情抽屉 */

function openDetail(poi) {
  state.selected = poi;
  $("d-name-en").textContent = poi.names.en || "";
  const pinyin = (poi.romanization || {}).pinyin;
  const pinyinRow = $("d-name-pinyin");
  pinyinRow.textContent = pinyin || "";
  pinyinRow.hidden = !pinyin;                       // 缺失时隐藏，不用 name 自动推导
  $("d-name-zh").textContent = poi.names["zh-Hans"] || "";
  $("d-introduction").textContent = poiIntroduction(poi);

  const rows = $("d-rows");
  rows.replaceChildren();
  for (const row of detailRows(poi)) {
    const classes = ["row"];
    if (row.warn) classes.push("warn");
    if (row.isDefault) classes.push("default-value");   // 参考值需要视觉标注
    const wrapper = element("div", classes.join(" "));
    wrapper.append(element("dt", "", row.label), element("dd", "", row.text || "—"));
    rows.append(wrapper);
  }

  const daySelect = $("d-day");
  daySelect.replaceChildren();
  if (state.trip) {
    for (const day of state.trip.days) {
      const option = element("option", "", `Day ${day.day_index}（${day.date}）`);
      option.value = String(day.day_index);
      daySelect.append(option);
    }
    daySelect.value = String(state.currentDayIndex);
  }
  const hasTrip = Boolean(state.trip);
  daySelect.disabled = !hasTrip;
  $("d-add").disabled = !hasTrip;
  $("d-hint").textContent = hasTrip ? "" : "请先在①创建行程，之后才能把 POI 加入某一天。";
  resetAddConfirmation();
  $("detail").showModal();
  redrawMap();                       // 选中态变化 → 图钉状态要跟着变
}

