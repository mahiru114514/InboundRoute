"use strict";
/* 用户流程：历史恢复、编辑、规则、路线与可携带的离线问路卡。 */
const flow = {evaluations: {}, routes: {}, offline: null, drag: null};

function rankPois(pois, interests) {
  const score = p => 0.6 * (interests.includes(p.category.level1) ? 1 / interests.length : 0)
    + 0.3 * (p.popularity_norm || 0) + 0.1 * ((p.provenance || {}).confidence || 0);
  return [...pois].sort((a,b) => (interests.length ? score(b)-score(a) : (b.popularity_norm||0)-(a.popularity_norm||0))
    || (a.names.en || '').localeCompare(b.names.en || ''));
}

function rememberTrip() {
  try { localStorage.setItem('inboundroute.lastTrip', state.trip.trip_id); } catch (_) { /* 私密模式仍可用历史列表 */ }
}

function tripDisplayName(trip) {
  const date = trip.start_date || trip.days?.[0]?.date;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || '');
  const departure = match ? `${match[1]}年${Number(match[2])}月${Number(match[3])}日出发` : '日期待设置';
  const days = trip.duration_days || trip.days?.length;
  return `上海 · ${departure} · ${days ? `${days}天` : '天数待设置'}`;
}

async function refreshHistory() {
  const data = await api('/api/trips');
  const select = $('trip-history');
  select.replaceChildren();
  const empty = element('option', '', '新建行程（填写①后保存）'); empty.value = ''; select.append(empty);
  const summaries = data.trips || (data.trip_ids || []).map(trip_id => ({trip_id}));
  const totals = new Map(), seen = new Map();
  for (const trip of summaries) {const name=tripDisplayName(trip);totals.set(name,(totals.get(name) || 0)+1);}
  for (const trip of summaries) {
    const name=tripDisplayName(trip), number=(seen.get(name) || 0)+1;seen.set(name,number);
    const option = element('option', '', name + (totals.get(name)>1 ? `（行程${number}）` : ''));
    option.value = trip.trip_id; select.append(option);
  }
  if (state.trip) select.value = state.trip.trip_id;
  const hint = $('history-hint');
  if (hint) {
    hint.textContent = summaries.length
      ? `共 ${summaries.length} 份已保存行程；刷新或重开页面会自动恢复上次编辑的那一份。`
      : '还没有已保存的行程：填写①后点「保存行程」。';
  }
  return summaries;
}

async function loadSavedTrip(id) {
  if (!id) {
    state.trip = null; state.currentDayIndex = 1;
    flow.evaluations = {}; flow.routes = {}; flow.offline = null;
    try { localStorage.removeItem('inboundroute.lastTrip'); } catch (_) {}
    resetSetup(); renderTrip(); renderPoiList(); renderFlow(); return;
  }
  const trip = await api(`/api/trips/${encodeURIComponent(id)}`);
  state.trip = trip; state.currentDayIndex = 1;
  flow.evaluations = {}; flow.routes = {}; flow.offline = null;
  formFromTrip(trip);
  rememberTrip(); renderTrip(); redrawMap(); renderPoiList();
  $('trip-history').value = id;
  renderFlow();
}

async function restoreHistory() {
  const trips = await refreshHistory();
  let id;
  try { id = localStorage.getItem('inboundroute.lastTrip'); } catch (_) {}
  if (!trips.some(t => t.trip_id === id)) id = trips[0]?.trip_id;
  const draft = loadDraft();
  if (draft?.trip_id === null) id = null;
  if (id) await loadSavedTrip(id);
  renderFlow();
  return trips;
}

async function flowAction(task) {
  if (state.busy) return;
  state.busy = true;
  document.body.setAttribute('aria-busy', 'true');
  try { await task(); }
  catch (error) { notify(error.message, true); }
  finally {
    state.busy = false;
    document.body.setAttribute('aria-busy', 'false');
    if (typeof renderRecommendations === 'function') renderRecommendations();
  }
}

/* 历史列表以前只能「选」，不能删也不能复制：想去掉一份旧行程只能去翻磁盘文件。 */

async function duplicateCurrentTrip() {
  if (!state.trip) return;
  const copy = await api(`/api/trips/${encodeURIComponent(state.trip.trip_id)}:duplicate`,
    {method:'POST', body:{}});
  await refreshHistory();
  await loadSavedTrip(copy.trip_id);
  await evaluateTrip();
  notify(`已复制为新行程：${tripDisplayName(copy)}`);
}

async function deleteCurrentTrip() {
  if (!state.trip) return;
  const id = state.trip.trip_id;
  const name = tripDisplayName(state.trip);
  // 桩环境 / 内嵌浏览器可能没有 confirm，缺了也要能删（否则按钮等于失效）。
  if (typeof window !== 'undefined' && typeof window.confirm === 'function'
      && !window.confirm(window.IRLanguage ? window.IRLanguage.translate(`确定删除“${name}”？此操作不可撤销。`) : `确定删除“${name}”？此操作不可撤销。`)) return;
  await api(`/api/trips/${encodeURIComponent(id)}`, {method:'DELETE'});
  state.trip = null;
  flow.evaluations = {}; flow.routes = {}; flow.offline = null;
  try { localStorage.removeItem('inboundroute.lastTrip'); } catch (_) { /* 忽略 */ }
  const trips = await refreshHistory();
  if (trips.length) {
    await loadSavedTrip(trips[0].trip_id);
  } else {
    // 一份都不剩：把行程相关的面板收回去，别留着上一份的残影。
    if (typeof renderTrip === 'function') renderTrip();
    renderFlow();
  }
  notify(`已删除行程：${name}`);
}

async function evaluateTrip(trigger = 'load_trip') {
  if (!state.trip) return;
  try {
    const result = await api(`/api/trips/${state.trip.trip_id}/rules:evaluate`,
      {method:'POST', body:{trigger, persist:true}});
    state.trip = result.trip;
    flow.evaluations = result;
    renderTrip(); redrawMap(); renderFlow();
  } catch (error) {
    flow.evaluations = {error: `规则未完成校验：${error.message}`};
    renderFlow();
    throw error;
  }
}

async function afterTripEdit(trigger) {
  flow.routes = {}; flow.offline = null;
  $('route-progress').textContent = '';
  if (typeof dayCards !== 'undefined') dayCards.progress.clear();
  rememberTrip(); renderTrip(); redrawMap(); renderPoiList(); renderFlow();
  await evaluateTrip(trigger);
}

function actionButton(label, action) {
  const button = element('button', 'secondary', label);
  button.type = 'button'; button.addEventListener('click', () => flowAction(action));
  return button;
}

async function saveDayStart(dayIndex,value) {
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(value)) throw new Error('请输入有效的出发时刻');
  const trip = state.trip;
  if (!trip) return;
  state.trip = await api(`/api/trips/${trip.trip_id}`, {method:'PATCH',version:trip.version,
    body:{days:[{day_index:dayIndex,daily_start_local:value}]}});
  delete flow.routes[dayIndex];flow.offline=null;flow.evaluations={};
  if (typeof dayCards !== 'undefined') dayCards.progress.delete(dayIndex);
  $('route-progress').textContent='';
  rememberTrip();renderTrip();redrawMap();renderFlow();
  if (engineReady('rules_engine')) await evaluateTrip('change_config');
  notify(`Day ${dayIndex} 出发时刻已保存为 ${value}；请重新计算当天交通。`);
}

async function saveDayAnchor(dayIndex,field,value) {
  if(!['start_anchor','end_anchor'].includes(field)) throw new Error('无效的每日地点');
  const trip=state.trip;if(!trip) return;
  const before=resolveDayPoints(trip);
  state.trip=await api(`/api/trips/${trip.trip_id}`,{method:'PATCH',version:trip.version,
    body:{days:[{day_index:dayIndex,[field]:value}]}});
  const after=resolveDayPoints(state.trip),affected=[];
  for(const day of state.trip.days) {
    const index=day.day_index;
    if(dayPointIdentity(before[index]?.start)!==dayPointIdentity(after[index]?.start)
      || dayPointIdentity(before[index]?.end)!==dayPointIdentity(after[index]?.end)) {
      delete flow.routes[index];affected.push(index);
      if(typeof dayCards!=='undefined') dayCards.progress.delete(index);
    }
  }
  flow.offline=null;flow.evaluations={};$('route-progress').textContent='';
  rememberTrip();renderTrip();redrawMap();renderFlow();
  if(engineReady('rules_engine')) await evaluateTrip('change_config');
  notify(affected.length ? `每日地点已保存；请重新计算 Day ${affected.join('、')} 的交通。` : '每日地点已保存，实际起终点没有变化，现有交通保留。');
}

async function reorderDay(dayIndex, ids) {
  const data = await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops`,
    {method:'PUT', body:{stop_order:ids}});
  state.trip = data.trip;
  await afterTripEdit('reorder');
}

/** 跨天移动控件：把景点挪到另一天（原来只能同一天内上下移动 / 拖拽）。 */
function addCrossDayControl(controls, day, stop) {
  const others = (state.trip.days || []).filter(item => item.day_index !== day.day_index);
  if (!others.length || stop.locked) return;   // locked 不许移动，与后端约束保持一致
  const picker = document.createElement('select');
  picker.className = 'move-day-target';
  picker.setAttribute('aria-label', `为第 ${stop.stop_order} 个景点选择目标日期`);
  for (const target of others) {
    const option = element('option', '', `Day ${target.day_index}（${target.date}）`);
    option.value = String(target.day_index);
    picker.append(option);
  }
  // 显式选中第一项：真实浏览器会自动选中，但取值不该依赖这个隐式行为
  // （否则读不到值时会发出 to_day_index=0，被后端判成「Day 0 不存在」）。
  const fallback = String(others[0].day_index);
  picker.value = fallback;
  const button = actionButton('移到该天', async () => {
    const toDay = Number(picker.value || fallback);
    if (!Number.isInteger(toDay) || toDay < 1) throw new Error('请选择要移到哪一天');
    const result = await api(
      `/api/trips/${state.trip.trip_id}/days/${day.day_index}/stops/${stop.stop_id || stop.poi_id}/move`,
      {method:'POST', body:{to_day_index: toDay}});
    state.trip = result.trip;
    if (result.pacing_warning) notify(result.pacing_warning);
    await afterTripEdit('change_day');
  });
  const wrap = element('span', 'move-day');
  wrap.append(picker, button);
  controls.append(wrap);
}

function addStopControls(item, day, stop) {
  const controls = element('div', 'stop-controls');
  for (const [label, offset] of [['上移', -1], ['下移', 1]]) {
    const button = actionButton(label, async () => {
      const ids = day.ordered_stops.map(s => s.stop_id || s.poi_id), index = ids.indexOf(stop.stop_id || stop.poi_id);
      [ids[index], ids[index+offset]] = [ids[index+offset], ids[index]];
      await reorderDay(day.day_index, ids);
    });
    button.disabled = stop.stop_order + offset < 1 || stop.stop_order + offset > day.ordered_stops.length;
    controls.append(button);
  }
  controls.append(actionButton(stop.locked ? '解锁' : '锁定', async () => {
    state.trip = await api(`/api/trips/${state.trip.trip_id}`, {method:'PATCH', version:state.trip.version,
      body:{days:[{day_index:day.day_index, ordered_stops:[{stop_order:stop.stop_order, locked:!stop.locked}]}]}});
    await afterTripEdit('change_config');
  }));
  const evening = actionButton('移到晚上', async () => {
    const result = await api(`/api/trips/${state.trip.trip_id}/days/${day.day_index}/stops/evening`,
      {method:'POST', body:{poi_id:stop.stop_id || stop.poi_id}});
    state.trip = result.trip; await afterTripEdit('move_to_evening');
  });
  evening.disabled = stop.locked; controls.append(evening);
  addCrossDayControl(controls, day, stop);
  item.append(controls);
  item.draggable = true;
  item.addEventListener('dragstart', event => {
    if (state.busy) {event.preventDefault(); return;}
    flow.drag = {day:day.day_index, id:stop.stop_id || stop.poi_id};
    event.dataTransfer.setData('text/plain', stop.stop_id || stop.poi_id);
  });
  item.addEventListener('dragover', event => {if (flow.drag?.day === day.day_index) event.preventDefault();});
  item.addEventListener('drop', event => {
    event.preventDefault();
    if (!flow.drag || flow.drag.day !== day.day_index || flow.drag.id === (stop.stop_id || stop.poi_id)) return;
    const ids = day.ordered_stops.map(s => s.stop_id || s.poi_id).filter(id => id !== flow.drag.id);
    ids.splice(ids.indexOf(stop.stop_id || stop.poi_id), 0, flow.drag.id); flow.drag = null;
    flowAction(() => reorderDay(day.day_index, ids));
  });
  item.addEventListener('dragend', () => {flow.drag = null;});
}

function noticeText(notice) {
  if (typeof reminderText === 'function') return reminderText(notice);
  const a = notice.message_args || {};
  const texts = {
    'rule.closure.confirm': `${a.poi_name}：${a.weekday} 闭馆，请确认是否保留。`,
    'rule.closure.reason': `${a.poi_name}：${a.reason}，请确认是否保留。`,
    'rule.closure.data_unknown': `${a.poi_name}：闭馆信息待确认。`,
    'rule.closure.data_unverified': `${a.poi_name}：闭馆信息尚未核实，请在出发前核对官方公告。`,
    'rule.lightup.too_early': `${a.poi_name || '夜景景点'}：到达早于亮灯时段，建议移到晚上。`,
    'rule.lightup.too_late': `${a.poi_name || '夜景景点'}：到达可能晚于亮灯结束。`,
    'rule.spread.long_transit': `相邻景点跨度 ${a.distance_km} km，交通约 ${a.duration_minutes} 分钟，建议分到其他天。`,
    'rule.homogeneous.banner': `当天有 ${a.count} 个同类景点（${a.category}），可以搭配其他类别。`
  };
  return texts[notice.message_key] || '有一条行程建议，请核对景点运营信息。';
}

/* 引擎是否就绪：未就绪时相关面板必须明说「为什么不能用」，而不是静默留白。 */
function engineReady(moduleId) {
  const services = state.services && state.services.services ? state.services.services : [];
  const found = services.find(item => item.module_id === moduleId);
  return found ? Boolean(found.ready) : false;
}

function routeUnavailableReason() {
  const service = state.services?.services?.find(item => item.module_id === 'route_adapter');
  return `路线服务未就绪：${service?.detail || '请先启动路线适配器'}。`;
}

function renderFlow() {
  if (typeof flow === 'undefined' || !$('rules-panel')) return;
  const hasTrip = Boolean(state.trip);
  // 删除 / 复制 / 载入设定只对「当前有一份行程」有意义，没有行程时必须禁用。
  for (const id of ['delete-trip', 'duplicate-trip']) {
    if ($(id)) $(id).disabled = !hasTrip;
  }
  $('edit-mode-hint').textContent = hasTrip
    ? '保存会更新当前行程并保留已排景点；重置恢复已保存设定。要另建行程，请在历史下拉选择“新建行程”。'
    : '填写后保存即可新建行程。';
  $('compute-all-routes').disabled = !hasTrip || !engineReady('route_adapter') || !state.trip?.days.some(d => typeof dayNeedsTransport === 'function' ? dayNeedsTransport(state.trip,d) : d.ordered_stops.length);
  $('rules-panel').hidden = !hasTrip;
  if ($('offline-panel')) $('offline-panel').hidden = !hasTrip;
  if (typeof updateSetupDisclosure === "function") updateSetupDisclosure(state.trip);
  if (!hasTrip) { $('route-hint').textContent = ''; $('route-progress').textContent = ''; return; }
  const rulesUp = engineReady('rules_engine'), routeUp = engineReady('route_adapter'), offlineUp = engineReady('offline_kit');
  const list = $('rule-notices'); list.replaceChildren();
  const result = flow.evaluations;
  if (typeof renderTripReminders === 'function') renderTripReminders(list,result,rulesUp);
  else {
  if (!rulesUp) list.append(element('p','warning','rules_engine 未就绪：无法校验闭馆与亮灯规则，这里不会给出结论。启动该模块后点「重新校验行程」。'));
  else if (result.error) list.append(element('p','warning',result.error));
  else if (!result.notices) list.append(element('p','hint','尚未校验。请点击“重新校验行程”，核对闭馆信息。'));
  for (const notice of result.notices || []) {
    const row = element('div', notice.severity === 'hard' ? 'rule-row warning' : 'rule-row');
    row.append(element('p','',noticeText(notice)));
    if (notice.severity === 'hard') {
      if (notice.outcome === 'confirmed_proceed') row.append(element('strong','','已确认保留，仍存在闭馆风险'));
      else {
        const id = notice.message_args.notice_id;
        row.append(actionButton('仍然保留', async () => {
          const data = await api(`/api/trips/${state.trip.trip_id}/conflicts/${encodeURIComponent(id)}/confirm`,
            {method:'POST',body:{decision:'proceed_anyway'}});
          state.trip = data.trip; await evaluateTrip();
        }), actionButton('移除此景点', async () => {
          const [,dayIndex,poiId] = id.split(':');
          const data = await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops/${poiId}`, {method:'DELETE'});
          state.trip = data.trip; await afterTripEdit('remove_stop');
        }));
      }
    }
    list.append(row);
  }
  if (rulesUp && result.notices && !result.notices.length) list.append(element('p','','已完成规则检查；未发现当前可判断的冲突。'));
  if (result.overflow) {
    // 就地展示有条数上限（契约的 channel 承载位），但不能让信息就此消失：
    // 被裁掉的建议由后端一并回传，这里提供「展开全部」。
    const row = element('div', 'rule-row');
    row.append(element('p','hint',
      `另有 ${result.overflow} 条非硬建议未就地展示（硬冲突已全部列出）。`));
    const extra = result.overflow_notices || [];
    if (extra.length) {
      const box = element('div','rule-extra'); box.hidden = true;
      for (const notice of extra) box.append(element('p','',noticeText(notice)));
      let open = false;
      const button = element('button','link-button',`展开全部建议（${extra.length} 条）`);
      button.type = 'button';
      button.addEventListener('click', () => {
        open = !open; box.hidden = !open;
        button.textContent = open ? '收起建议' : `展开全部建议（${extra.length} 条）`;
      });
      row.append(button, box);
    }
    list.append(row);
  }
  if (result.skipped_rules?.length) list.append(element('p','warning','部分规则缺少数据，尚不能完整校验；请先计算区间交通并核实景点时间。'));
  }
  const routeHint = $('route-hint');
  const computedRoutes = Object.values(flow.routes).flat();
  routeHint.className = routeUp ? 'hint' : 'hint warning';
  routeHint.textContent = !routeUp ? routeUnavailableReason()
    : !state.trip.days.some(d => typeof dayNeedsTransport === 'function' ? dayNeedsTransport(state.trip,d) : d.ordered_stops.length) ? '请先加入景点或设置不同起终点，再计算交通。'
    : !computedRoutes.length ? '点击“计算全部区间交通”，或展开某一天单独计算；交通方案在当天详情中查看。'
    : `已计算 ${computedRoutes.length} 个区段，展开每日卡片查看和选择交通方式。` +
      (computedRoutes.some(r=>r.partial || r.duration_seconds == null) ? '部分方式不可用，请查看当天问题提示。' : '');
  $('offline-status').textContent = !offlineUp
    ? 'offline_kit 未就绪：无法生成离线包；启动该模块后重新生成。'
    : flow.offline ? '离线包已载入。行程编辑后请重新生成；有效期 24 小时。'
    : '生成前请完成闭馆确认及交通计算。可下载 HTML，在关闭本地服务后打开问路卡。';
  if (typeof syncDayCards === "function") syncDayCards();
}

async function computeDayRoutes(dayIndex) {
  if (!state.trip) return false;
  const tripId = state.trip.trip_id;
  const day = state.trip.days.find(d => d.day_index === dayIndex);
  const progress = text => { $('route-progress').textContent = text; if (typeof setDayRouteProgress === 'function') setDayRouteProgress(dayIndex,text); };
  const results = [];
  const profile = state.trip.user_profile;
  if (!day || !(typeof dayNeedsTransport === 'function' ? dayNeedsTransport(state.trip,day) : day.ordered_stops.length)) { progress(`Day ${dayIndex} 没有景点且起终点相同，无需计算交通。`); return false; }
  if (!engineReady('route_adapter')) { progress(routeUnavailableReason()); return false; }
  const total = day.ordered_stops.length + 1;
  for (let i=0; i < total; i++) {
    progress(`Day ${dayIndex}：计算区间 ${i+1}/${total}…`);
    let result;
    try {
      result = await api(`/api/trips/${tripId}/days/${dayIndex}/routes:compute`,
        {method:'POST', body:{segment_index:i, party_composition:profile.party_composition, prefer_taxi:profile.prefer_taxi}});
    } catch (error) {
      // 中途失败不能把半截结果当成完整方案：明确说明停在哪一段。
      progress(`Day ${dayIndex}：第 ${i+1}/${total} 段计算失败——${error.message}。已保留前面算出的区段。`);
      flow.routes[dayIndex] = results; flow.offline = null; renderFlow(); return false;
    }
    if (result.routes[0]) results.push(result.routes[0]);
  }
  flow.routes[dayIndex] = results;
  // 优先打车的用户选择打车；其他用户选择公共交通。仅保存有时间数据的路线。
  for (let i=0; i<results.length; i++) {
    let route = results[i];
    if (profile.prefer_taxi && route?.variants?.some(v => v.mode === 'taxi' && v.duration_seconds != null)) {
      route = withRouteAlternatives(await fetchMode(dayIndex,i,'taxi'),route); results[i] = route;
    }
    if (route?.duration_seconds != null) await saveRoute(dayIndex,i,route);
  }
  progress(results.some(r => r.data_source === 'mock') ? '计算完成，包含演示路线，请勿用于真实导航。' : '计算完成，可选择其他交通方式；请核实实时交通。');
  flow.offline = null;
  await evaluateTrip();
  return true;
}

async function computeAllRoutes() {
  const days = (state.trip?.days || []).filter(d => typeof dayNeedsTransport === 'function' ? dayNeedsTransport(state.trip,d) : d.ordered_stops.length).map(d => d.day_index);
  for (const dayIndex of days) if (!await computeDayRoutes(dayIndex)) return;
  const routes = Object.values(flow.routes).flat();
  $('route-progress').textContent = `已计算 ${days.length} 天、${routes.length} 个区段。` +
    (routes.some(r => r.data_source === 'mock') ? '包含演示路线，请勿用于真实导航。' : routes.some(r => r.partial) ? '部分交通方式不可用；请选择可用方案补齐时间轴。' : '请核实实时交通。');
}

async function fetchMode(dayIndex,index,mode) {
  const result = await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/routes:compute`,
    {method:'POST',body:{segment_index:index,modes:[mode],party_composition:state.trip.user_profile.party_composition}});
  return result.routes[0];
}

// 单方式请求只返回该方式；保存前合并已有候选，刷新后仍能切换。
function withRouteAlternatives(selected, previous) {
  const fresh = selected.variants || [];
  const variants = (previous?.variants || fresh).map(v => ({
    ...(fresh.find(next => next.mode === v.mode) || v),is_default_tab:v.mode === selected.mode
  }));
  return {...selected,variants,partial:Boolean(selected.partial || variants.some(v=>v.duration_seconds == null))};
}

async function saveRoute(dayIndex,index,route) {
  const day = state.trip.days.find(d=>d.day_index===dayIndex);
  if (!day || index < 0 || index > day.ordered_stops.length) throw new Error('交通区段不存在');
  const change = index === day.ordered_stops.length ? {end_transit:route} : {ordered_stops:[{stop_order:index+1,transit_from_previous:route}]};
  state.trip = await api(`/api/trips/${state.trip.trip_id}`, {method:'PATCH',version:state.trip.version,
    body:{days:[{day_index:dayIndex,...change}]}});
}

function renderRoute(container, dayIndex,index,route) {
  const card = element('article','route-card');
  const endpoints=element('strong','',`${route.from.name_zh || '起点'} → ${route.to.name_zh || '终点'}`);
  if(route.from.name_zh && route.to.name_zh)endpoints.setAttribute('data-i18n-ignore','');
  if(typeof bindDaySequence==='function') {bindDaySequence(endpoints,[route.from,route.to]);refreshPlaceNameNodes();}
  card.append(endpoints);
  const modes = {transit:'公共交通',taxi:'打车',walk:'步行'};
  const needsChoice = route.duration_seconds == null && (route.variants || []).some(v => v.duration_seconds != null);
  card.append(element('p', route.data_source === 'mock' || route.partial ? 'warning' : 'hint',
    needsChoice ? `${modes[route.mode] || route.mode}暂不可用，请选择下方可用方案${route.data_source === 'mock' ? '（演示路线，非真实导航）' : ''}` :
    route.data_source === 'mock' ? '演示路线 · 非真实导航' : route.data_source === 'degraded' ? '路线不可用，请检查服务配置或稍后重试' : `来源：${route.data_source}`));
  const day = state.trip.days.find(d => d.day_index === dayIndex);
  for (const variant of route.variants || []) {
    const seconds = variant.duration_seconds;
    const text = `${modes[variant.mode] || variant.mode} · ${seconds == null ? '暂无耗时' : Math.ceil(seconds/60)+' 分钟'}${variant.distance_meters == null ? '' : ' · '+(variant.distance_meters/1000).toFixed(1)+' km'}${variant.cost ? ' · ¥'+variant.cost.min+'–'+variant.cost.max : ''}`;
    const button = actionButton(text, async () => {
      const selected = await fetchMode(dayIndex,index,variant.mode);
      if (!selected || selected.duration_seconds == null) throw new Error('该方式暂不可用，已保留原方案');
      const merged = withRouteAlternatives(selected,route);
      await saveRoute(dayIndex,index,merged);
      if (!flow.routes[dayIndex]) flow.routes[dayIndex] = [];
      flow.routes[dayIndex][index] = merged;
      flow.offline = null; await evaluateTrip();
    });
    button.disabled = seconds == null;
    card.append(button);
  }
  if (route.has_long_transfer) card.append(element('p','warning','换乘步行较长，时间轴已计入额外步行时间。'));
  const adopted = day.ordered_stops[index]?.transit_from_previous?.mode || (route.duration_seconds != null ? route.mode : null);
  card.append(element('p','hint',`当前采用：${adopted ? modes[adopted] || adopted : '未选择可用方案'}`));
  if (typeof renderRouteNavigation === 'function') renderRouteNavigation(card,dayIndex,index,route);
  container.append(card);
}

async function generateOffline() {
  await evaluateTrip();
  if (flow.evaluations.notices.some(n => n.severity === 'hard' && n.outcome !== 'confirmed_proceed'))
    throw new Error('请先处理闭馆冲突：选择仍然保留或移除景点');
  if (state.trip.days.some(d => d.ordered_stops.some(s => s.arrival_at == null || s.departure_at == null || s.transit_from_previous?.duration_seconds == null)))
    throw new Error('请先计算各天交通路线，再生成离线包');
  const pkg = await api(`/api/trips/${state.trip.trip_id}/offline-package`, {method:'POST',body:{}});
  pkg.trip_id = state.trip.trip_id;
  flow.offline = pkg;
  try { await InboundRouteOfflineCache.save(pkg); }
  catch (error) {notify(`浏览器缓存失败：${error.message}。仍可下载离线文件。`,true);}
  renderOffline(pkg); renderFlow();
}
function renderOffline(pkg,updateEditor=true) {
  $('offline-preview').innerHTML = offlineContent(pkg); // All data escaped above; no remote HTML.
  if(updateEditor && typeof renderPlaceTranslationEditor==='function') renderPlaceTranslationEditor(pkg);
}
function downloadOffline() {
  const pkg = flow.offline;
  if (pkg && typeof placeNames!=='undefined' && placeNames.translationVersion && pkg.payload?.translation_version!==placeNames.translationVersion) throw new Error('地名译文已更新，请重新生成离线包');
  if (!pkg || pkg.trip_version !== state.trip.version) throw new Error('请重新生成或读取当前版本离线包');
  const html = offlineDocument(pkg);
  const url = URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));
  const a = document.createElement('a'); a.href=url; a.download=`${pkg.trip_id}-offline.html`;
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
}
async function initFlow() {
  window.addEventListener?.('inboundroute:languagechange',()=>{if (flow.offline) renderOffline(flow.offline,false);});
  $('trip-history').addEventListener('change',event => flowAction(async () => {discardDraft(); await loadSavedTrip(event.target.value); await evaluateTrip();}));
  $('refresh-history').addEventListener('click',() => flowAction(refreshHistory));
  $('delete-trip').addEventListener('click',() => flowAction(deleteCurrentTrip));
  $('duplicate-trip').addEventListener('click',() => flowAction(duplicateCurrentTrip));
  $('compute-all-routes').addEventListener('click', () => flowAction(computeAllRoutes));
  $('evaluate-trip').addEventListener('click',() => flowAction(() => evaluateTrip()));
  $('generate-offline').addEventListener('click',() => flowAction(generateOffline));
  $('download-offline').addEventListener('click',() => flowAction(async () => downloadOffline()));
  $('load-offline').addEventListener('click',() => flowAction(async () => {
    const loaded = await InboundRouteOfflineCache.load(state.trip.trip_id,state.trip.version,typeof placeNames!=='undefined' ? placeNames.translationVersion : null);
    if (!loaded.found) throw new Error('当前浏览器没有此行程的离线包');
    flow.offline = {trip_id:state.trip.trip_id,package_version:loaded.package_version,ttl_hours:loaded.ttl_hours,trip_version:loaded.trip_version,generated_at:loaded.generated_at,payload:loaded.offline_data};
    renderOffline(flow.offline); renderFlow();
    if (loaded.reason==='translation_mismatch') $('offline-status').textContent='地名译文已更新，请重新生成并下载离线卡片。';
    else if (loaded.stale) $('offline-status').textContent = '离线包已过期或行程有修改，请重新生成；下方显示的是旧快照。';
  }));
  try {
    // 历史恢复是页面能不能用的前提：失败必须在①的提示行说明原因，不能静默留空。
    await restoreHistory();
  } catch (error) {
    if ($('history-hint')) $('history-hint').textContent = `无法读取已保存行程：${error.message}（trip_engine 未就绪时属预期降级）`;
    if ($('rules-panel')) $('rules-panel').hidden = true;
    return;
  }
  if (state.trip) await evaluateTrip();
}


async function addAnchorStop(dayIndex,anchor,stopOrder,dwellMinutes=0,hotelStayKind=null) {
  const result=await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops`,{method:'POST',
    body:{stop_type:anchor.type,anchor,stop_order:stopOrder,planned_dwell_minutes:dwellMinutes,
      ...(anchor.type === 'hotel' && hotelStayKind != null ? {hotel_stay_kind:hotelStayKind} : {})}});
  state.trip=result.trip;
  await afterTripEdit('add_stop');
}
