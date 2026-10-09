"use strict";
/* 景点筛选、排序和列表；依赖 runtime、poi_content、poi_details、map_view。 */

/* ---------------------------------------------------------------- POI 列表与示意地图 */

function wirePoiScroll() {
  const list = $("poi-list");
  const toggle = $("poi-auto-scroll");
  let automatic = false, frame = null, previous = null, position = 0, direction = 1;
  function setAutomatic(value) {
    automatic = value;
    if (frame !== null) window.cancelAnimationFrame?.(frame);
    frame = null;
    previous = null;
    position = list.scrollLeft;
    toggle.textContent = value ? '暂停自动滚动' : '恢复自动滚动';
    if (value) frame = window.requestAnimationFrame(tick);
  }
  function tick(time) {
    if (!automatic) return;
    const rect = list.getBoundingClientRect();
    const maximum = Math.max(0, list.scrollWidth - list.clientWidth);
    if (!document.hidden && rect.bottom > 0 && rect.top < window.innerHeight && maximum > 0) {
      const elapsed = previous === null ? 0 : Math.min(time - previous, 50);
      position = Math.min(maximum, Math.max(0, position + direction * elapsed * 0.03));
      list.scrollLeft = position;
      if (position >= maximum) direction = -1;
      else if (position <= 0) direction = 1;
      previous = time;
    } else previous = null;
    frame = window.requestAnimationFrame(tick);
  }
  toggle.addEventListener('click', () => setAutomatic(!automatic));
  // 手动浏览持续接管，只有明确点击恢复才重新自动滚动。
  for (const type of ['pointerdown', 'focusin']) list.addEventListener(type, () => setAutomatic(false));
  list.addEventListener("wheel", event => {
    // 横向触控板交给浏览器；Ctrl+滚轮保留缩放。纵向滚轮只在列表仍可移动时接管。
    if (event.ctrlKey || (!event.deltaX && !event.deltaY)) return;
    setAutomatic(false);
    if (event.deltaX || !event.deltaY) return;
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientWidth : 1;
    const maximum = Math.max(0, list.scrollWidth - list.clientWidth);
    const next = Math.min(maximum, Math.max(0, list.scrollLeft + event.deltaY * unit));
    if (Math.abs(next - list.scrollLeft) < 1) return;
    event.preventDefault();
    list.scrollLeft = next;
  }, {passive:false});
  if (window.requestAnimationFrame && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) setAutomatic(true);
}

function visiblePois() {
  const keyword = ($("poi-search").value || "").trim().toLowerCase();
  const category = $("poi-category").value;
  const filtered = state.pois.filter((poi) => {
    if (category && poi.category.level1 !== category) return false;
    if (!keyword) return true;
    const roman = poi.romanization || {};
    const haystack = [poi.names["zh-Hans"], poi.names.en, roman.pinyin, roman.pinyin_plain,
      ...(poi.search_aliases || [])].join(" ").toLowerCase();
    return haystack.includes(keyword);
  });
  // 兴趣必须真的影响排序（否则「兴趣」只是个被存起来没人用的字段）。
  // rankPois 在 flow.js：0.6×兴趣命中 + 0.3×热度 + 0.1×数据可信度，无兴趣时按热度。
  const interests = (state.trip && state.trip.user_profile && state.trip.user_profile.interests) || [];
  return typeof rankPois === "function" ? rankPois(filtered, interests) : filtered;
}

/** 地图上应该显示哪些 POI。
 *
 *  必须与右侧列表用**同一套筛选结果**：以前地图直接画 state.pois（只按视野模式裁），
 *  于是搜索/类别只过滤列表，图钉不动，两边对不上。
 */
function mapPois() {
  const matched = visiblePois();
  if (state.showAllPois) return matched;
  return matched.filter((poi) => state.isDensePoint(poi.coordinate));
}

function renderPoiList() {
  const list = $("poi-list");
  list.replaceChildren();
  const interests = (state.trip && state.trip.user_profile && state.trip.user_profile.interests) || [];
  const hint = $("poi-hint");
  if (hint) {
    hint.textContent = interests.length
      ? `已按兴趣排序：${interests.join("、")}（命中的类别排在前面，其余按热度）。`
      : "未选择兴趣，当前按热度排序；在①里勾选兴趣会改变这里的顺序。";
  }
  const pois = visiblePois();
  if (!pois.length) {
    list.append(element("li", "empty-day", "没有匹配的 POI"));
    // 列表空了，地图也要跟着空 —— 两边必须一致。
    redrawMap();
    return;
  }
  for (const poi of pois) {
    const item = element("li", "poi");
    item.dataset.category = poi.category.level1;
    const art = element("div", "poi-art");
    art.setAttribute("aria-label", "暂无景点照片");
    art.append(element("span", "poi-initial", poi.names["zh-Hans"].slice(0, 1)),
      element("small", "", "暂无照片"));
    const copy = element("div", "poi-copy");
    const category = poi.category.label_zh || poi.category.level2;
    const dwell = poi.operating_rules?.dwell_time;
    const minutes = dwell?.minutes_max || dwell?.minutes || dwell?.minutes_min;
    const summary = [category, ...(poi.tags || []).slice(0, 2), minutes ? `建议游览 ${minutes} 分钟` : "游览时长待核实"].join(" · ");
    const name = element('strong', '', poi.names['zh-Hans']);name.setAttribute('data-i18n-ignore','');
    copy.append(name, element("span", "poi-en", poi.names.en),
      element("p", "poi-summary", summary), element("p", "poi-introduction", poiIntroduction(poi)));
    item.append(art, copy);
    const open = element("button", "link-button", "详情");
    open.addEventListener("click", () => openDetail(poi));
    copy.append(open);
    list.append(item);
  }
  // 图钉跟着筛选结果走（搜索 / 类别变化时列表和地图必须同时变）。
  redrawMap();
  updateMapHint();
}

/** 示意地图：把经纬度线性映射到一个矩形区域（仅在未配置高德 key 时使用）。 */
