/* 每日概览：摘要始终可见；展开本身不调用接口。依赖 poi_content，节点引用用于无变化的服务轮询。 */
const dayCards = {tripId:null, open:new Set(), nodes:new Map(), setupTripId:undefined, progress:new Map()};

function dayDepartureSetting(trip, day) {
  const activity = trip.anchor_arrival?.activity_start_at;
  const firstDay = day.day_index === 1 && activity != null;
  const earliest = firstDay ? hhmm(activity) : null;
  const activityDate = firstDay && typeof ymd === 'function' ? ymd(activity) : null;
  const arrivalOnly = !!(activityDate && activityDate > day.date);
  const value = firstDay && (arrivalOnly || earliest > day.daily_start_local) ? earliest : day.daily_start_local;
  return {firstDay,earliest,activityDate,arrivalOnly,value};
}

function dayCardSummary(trip, day) {
  const stops = day.ordered_stops || [];
  const missing = stops.filter(s => s.transit_from_previous?.duration_seconds == null).length;
  const complete = stops.length > 0 && stops.every(s => s.arrival_at != null && s.departure_at != null);
  const notices = stops.flatMap(s => s.rule_notices || []);
  const identities = new Set(notices.filter(n => n.severity === 'hard').map(n =>
    n.message_args?.notice_id || JSON.stringify(n)));
  const evaluations = typeof flow === 'undefined' ? {} : flow.evaluations;
  const rulesLabel = !engineReady('rules_engine') ? '行程提醒暂不可用' : evaluations.error ? '行程检查未完成'
    : !evaluations.notices ? '行程待检查' : evaluations.skipped_rules?.length ? '部分检查资料待补充' : '已检查行程提醒';
  const departure = dayDepartureSetting(trip,day);
  const start = departure.value;
  return {count:stops.filter(s=>(s.stop_type || 'poi')==='poi').length,stopCount:stops.length,missing,complete,conflicts:identities.size,rulesLabel,
    dwell:stops.reduce((total,s)=>total+(s.planned_dwell_minutes || 0),0),
    time:complete ? `${hhmm(stops[0].arrival_at)}–${hhmm(stops[stops.length-1].departure_at)}`
      : departure.arrivalOnly ? `抵达与入住 · ${departure.activityDate} ${start} 缓冲结束`
      : stops.length ? `${start} 出发 · 结束待定` : `${start} 出发`};
}

function dayPoiName(stop) {
  if (typeof placeDisplayName === 'function') return placeDisplayName(stop);
  return stop.name_zh || state.pois.find(p => p.poi_id === stop.poi_id)?.names['zh-Hans'] || stop.poi_id || '停靠点';
}

function updateSetupDisclosure(trip) {
  const disclosure = $('setup-disclosure');
  const id = trip?.trip_id || null;
  if (dayCards.setupTripId !== id && $('route-progress')) $('route-progress').textContent = '';
  if (!trip) {dayCards.tripId=null;dayCards.open.clear();dayCards.nodes.clear();dayCards.progress.clear();}
  if (disclosure && dayCards.setupTripId !== id) disclosure.open = !trip;
  dayCards.setupTripId = id;
  const label = $('setup-summary-note');
  if (label) label.textContent = trip ? `${trip.days.length} 天 · 点击修改日期、住宿与偏好` : '填写日期、住宿与出行偏好';
}

function wireDayCardNavigation() {
  for (const link of document.querySelectorAll('a[href="#setup-panel"]')) {
    link.addEventListener('click', () => { const d = $('setup-disclosure'); if (d) d.open = true; });
  }
}

function renderDayCards(trip, container) {
  if (dayCards.tripId !== trip.trip_id) {dayCards.open.clear();dayCards.progress.clear();dayCards.tripId = trip.trip_id;}
  dayCards.nodes.clear();
  for (const day of trip.days) {
    const card = element('details','day ' + day.day_status);
    card.dataset.dayIndex = String(day.day_index);
    card.dataset.tone = ['mint','blue','apricot','lilac','rose','aqua'][(day.day_index-1)%6];
    card.open = dayCards.open.has(day.day_index);
    const summary = element('summary','day-summary');
    const head = element('div','day-head');
    head.append(element('strong','day-number',`Day ${day.day_index}`),
      element('span','day-date',`${day.date} ${weekdayZh(day.date)}`),element('span','day-chevron',card.open ? '收起详情' : '查看详情'));
    const points = typeof resolveDayPoints === 'function' ? resolveDayPoints(trip)[day.day_index] : {};
    const nameOf=p=>typeof placeDisplayName==='function' ? placeDisplayName(p) : p?.name_zh;
    const sequence=[nameOf(points.start),...day.ordered_stops.map(dayPoiName),nameOf(points.end)].filter(Boolean);
    const names = element('p','day-sequence',sequence.length ? sequence.join(' → ')
      : day.day_status === 'arrival_only' ? '抵达与入住' : '还没有安排景点');
    if (sequence.length) {
      names.setAttribute('data-i18n-ignore','');
      if(typeof bindDaySequence==='function') bindDaySequence(names,[points.start,...day.ordered_stops,points.end]);
    }
    const metrics = element('p','day-metrics');
    const statuses = element('div','day-statuses');
    summary.append(head,names,metrics,statuses);card.append(summary);
    const content = element('div','day-content');
    const timeline = element('div','day-timeline');
    const departureBox = element('label','day-start-setting','当天出发时刻');
    const departureInput = element('input','day-start-input');
    departureInput.type='time';departureInput.required=true;
    departureInput.setAttribute('aria-label',`Day ${day.day_index} 出发时刻`);
    const {firstDay,earliest,arrivalOnly,value:saved} = dayDepartureSetting(trip,day);
    departureInput.value = saved;
    departureInput.disabled = arrivalOnly;
    if (firstDay && !arrivalOnly) departureInput.min = earliest;
    departureInput.addEventListener('change',()=>{
      if (departureInput.value === saved) return;
      if (state.busy) {departureInput.value=saved;notify('正在处理上一项修改，请稍后再试。');return;}
      if (!departureInput.value || (earliest && departureInput.value < earliest)) {
        departureInput.value=saved;notify(firstDay ? `抵达当天最早 ${earliest} 出发。` : '请输入有效的出发时刻。',true);return;
      }
      flowAction(async()=>{try {await saveDayStart(day.day_index,departureInput.value);}
        catch(error) {departureInput.value=saved;throw error;}});
    });
    departureBox.append(departureInput);timeline.append(departureBox,
      element('p','hint',arrivalOnly ? '这一天只安排抵达与入住，游览从次日开始。'
        : firstDay ? `最早 ${earliest} 出发；修改后自动保存并重新校验，请重算当天交通。`
        : '每一天可设不同时间；修改后自动保存并重新校验，请重算当天交通。'));
    if (typeof renderDayPoints === 'function') renderDayPoints(trip,day,timeline);
    if (typeof renderAnchorStopPicker === 'function') renderAnchorStopPicker(trip,day,timeline);
    timeline.append(element('h3','','当天时间轴'),element('p','hint','调整景点顺序或交通方式后，时间轴会重新校验。'));
    const riskNotes = element('div','day-risk-notes');
    const uniqueRisks = new Map(day.ordered_stops.flatMap(s=>s.rule_notices || []).filter(n=>n.severity === 'hard')
      .map(n=>[n.message_args?.notice_id || JSON.stringify(n),n]));
    for (const notice of uniqueRisks.values()) riskNotes.append(element('p','warning',typeof noticeText === 'function' ? noticeText(notice) : '存在闭馆 / 时间风险，请检查开放信息。'));
    if (uniqueRisks.size) {const link = element('a','risk-link','查看并处理时间冲突');link.href='#rules-panel';riskNotes.append(link);}
    timeline.append(riskNotes);
    const list = element('ol','stop-list');
    const stopTimes = [];
    for (const stop of day.ordered_stops) {
      const item = element('li','stop');
      const time = element('span','stop-time');stopTimes.push(time);
      const copy = element('div','stop-copy');
      const stopName=element('span','stop-name',dayPoiName(stop));
      if(typeof placeNameNode==='function') placeNameNode(stopName,stop);
      copy.append(stopName);
      if ((stop.stop_type || 'poi') === 'poi') {
        copy.append(element('p','poi-introduction',poiIntroduction(state.pois.find(p=>p.poi_id===stop.poi_id))));
      }
      item.append(element('span','stop-order',String(stop.stop_order)),copy,
        element('span','stop-dwell',`${stop.stop_type === 'hotel' ? stop.hotel_stay_kind === 'rest' ? '休息' : '过夜住宿' : '停留'} ${stop.planned_dwell_minutes} 分钟`),time);
      if (stop.locked) item.append(element('span','stop-locked','已固定'));
      const remove = element('button','link-button','移除');remove.type='button';
      remove.addEventListener('click',()=>removeStop(day.day_index,stop.stop_id || stop.poi_id));item.append(remove);
      if (typeof addStopControls === 'function') addStopControls(item,day,stop);
      list.append(item);
    }
    timeline.append(list);
    if (!day.ordered_stops.length) timeline.append(element('p','empty-day','在“挑选景点”中将景点加入这一天。'));
    const traffic = element('div','day-traffic');
    traffic.append(element('h3','','当天区间交通'));
    const compute = element('button','secondary',`计算 Day ${day.day_index} 交通`);compute.type='button';
    compute.addEventListener('click',()=>flowAction(()=>computeDayRoutes(day.day_index)));
    const progress = element('p','hint',dayCards.progress.get(day.day_index) || '');progress.setAttribute('role','status');
    const routes = element('div','day-routes');
    traffic.append(compute,progress,routes);content.append(timeline,traffic);card.append(content);
    const collapse=element('button','secondary day-collapse','收起详情');collapse.type='button';
    collapse.addEventListener('click',()=>{card.open=false;dayCards.open.delete(day.day_index);
      head.children[2].textContent='查看详情';summary.focus?.();card.scrollIntoView?.({block:'start',behavior:'smooth'});});
    content.append(collapse);
    card.addEventListener('toggle',()=>{
      if (dayCards.nodes.get(day.day_index)?.card !== card) return;
      head.children[2].textContent = card.open ? '收起详情' : '查看详情';
      if (card.open) {
        const changed = !dayCards.open.has(day.day_index);
        dayCards.open.add(day.day_index);if (changed) setCurrentDay(day.day_index);
      }
      else dayCards.open.delete(day.day_index);
    });
    dayCards.nodes.set(day.day_index,{card,metrics,statuses,compute,routes,stopTimes,progress,routeSignature:null,statusSignature:null});
    container.append(card);
  }
  syncDayCards();
}

function syncDayCards() {
  if (!state.trip || dayCards.tripId !== state.trip.trip_id) return;
  for (const day of state.trip.days) {
    const nodes = dayCards.nodes.get(day.day_index);if (!nodes) continue;
    const summary = dayCardSummary(state.trip,day);
    const computed = typeof flow === 'undefined' ? null : flow.routes[day.day_index];
    const routes = day.ordered_stops.map((s,i)=>computed?.[i] || s.transit_from_previous);
    const tail = computed?.[day.ordered_stops.length] || day.end_transit;
    if (tail) routes.push(tail);
    const tailPending = summary.stopCount && tail?.duration_seconds == null;
    const limited = (computed || []).filter(r=>r && (r.partial || r.duration_seconds == null)).length;
    const mock = routes.some(r=>r?.data_source === 'mock');
    const sig = JSON.stringify([summary,tailPending,limited,mock,engineReady('route_adapter')]);
    if (sig !== nodes.statusSignature) {
      nodes.metrics.textContent = `${summary.count} 个景点 · ${summary.stopCount-summary.count} 项住宿 / 口岸 · 停留 ${summary.dwell} 分钟 · ${summary.complete ? '游览 ' : ''}${summary.time}`;
      nodes.statuses.replaceChildren();
      if (summary.stopCount) {
        nodes.statuses.append(element('span',summary.missing ? 'badge pending' : 'badge ready',summary.missing ? `${summary.missing} 段交通待补` : '去程交通已选'),
          element('span',tailPending ? 'badge pending' : 'badge ready',tailPending ? '返程待计算' : '返程已计算'),
          element('span',summary.complete ? 'badge ready' : 'badge pending',summary.complete ? '时间轴已生成' : '时间轴待补齐'));
      }
      if (limited) nodes.statuses.append(element('span','badge pending',`${limited} 段交通方式受限`));
      if (mock) nodes.statuses.append(element('span','badge pending','含演示路线'));
      if (summary.conflicts) nodes.statuses.append(element('span','badge risk',`${summary.conflicts} 条闭馆 / 时间风险`));
      if (summary.stopCount) nodes.statuses.append(element('span',summary.rulesLabel === '已检查行程提醒' ? 'badge neutral' : 'badge pending',summary.rulesLabel));
      else nodes.statuses.append(element('span','badge neutral',dayStatusLabel(day)));
      nodes.compute.disabled = !(typeof dayNeedsTransport === 'function' ? dayNeedsTransport(state.trip,day) : summary.count) || !engineReady('route_adapter');
      nodes.statusSignature = sig;
    }
    day.ordered_stops.forEach((s,i)=>{
      if (nodes.stopTimes[i]) nodes.stopTimes[i].textContent = s.arrival_at != null
        ? `${hhmm(s.arrival_at)} 抵达${s.departure_at != null ? ' · '+hhmm(s.departure_at)+' 离开' : ''}`
        : summary.missing ? '待补齐交通后计算' : '等待更新到达时间';
    });
    const routeSig = JSON.stringify([routes,engineReady('route_adapter')]);
    if (nodes.routeSignature === routeSig) continue;
    nodes.routes.replaceChildren();
    if (!engineReady('route_adapter')) nodes.routes.append(element('p','warning',typeof routeUnavailableReason === 'function' ? routeUnavailableReason() : '路线服务未就绪，请检查模块配置。'));
    if (!routes.some(Boolean)) nodes.routes.append(element('p','hint',summary.count || (typeof dayNeedsTransport === 'function' && dayNeedsTransport(state.trip,day))
      ? '还没有交通方案。点击上方按钮计算这一天。' : '加入景点或设置不同起终点后可以计算交通。'));
    routes.forEach((route,index)=>{if (route) renderRoute(nodes.routes,day.day_index,index,route);});
    if (!computed?.length && routes.some(Boolean) && !tail) nodes.routes.append(element('p','hint','已恢复保存的去程方案；当天终点区间请重新计算。'));
    nodes.routeSignature = routeSig;
  }
}

function setDayRouteProgress(dayIndex,text) {
  dayCards.progress.set(dayIndex,text);
  const nodes = dayCards.nodes.get(dayIndex);if (nodes) nodes.progress.textContent = text;
}
