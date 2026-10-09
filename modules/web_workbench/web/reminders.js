/* 将规则结果整理为用户能定位、能处理的行程提醒。 */
function reminderContext(notice) {
  const a=notice.message_args || {},id=(a.notice_id || '').split(':');
  const poi=(state.pois || []).find(p=>p.poi_id===(a.poi_id || id[2]))
    || (state.pois || []).find(p=>a.poi_name && Object.values(p.names || {}).includes(a.poi_name));
  const candidates=(state.trip?.days || []).filter(d=>d.ordered_stops.some(s=>s.poi_id===poi?.poi_id));
  const dayIndex=a.day_index || Number(id[1]) || (candidates.length===1 ? candidates[0].day_index : null);
  const day=state.trip?.days.find(d=>d.day_index===dayIndex);
  const stop=day?.ordered_stops.find(s=>s.poi_id===poi?.poi_id);
  return {day,dayIndex,poi,stop,name:poi?.names?.['zh-Hans'] || a.poi_name_zh || a.poi_name || ''};
}

function reminderModel(notice) {
  const a=notice.message_args || {},c=reminderContext(notice),key=notice.message_key;
  const title=[c.dayIndex ? `第${c.dayIndex}天` : '',c.day?.date || a.date,c.name].filter(Boolean).join(' · ') || '行程安排';
  const time=a.arrival_local || (c.stop?.arrival_at!=null ? hhmm(c.stop.arrival_at) : null);
  const weekdays={Monday:'周一',Tuesday:'周二',Wednesday:'周三',Thursday:'周四',Friday:'周五',Saturday:'周六',Sunday:'周日'};
  const choice=notice.outcome==='confirmed_proceed' ? '' : '请选择保留或移除。';
  let group='suggest',body='请检查这一天的安排和景点开放信息。',sourceNote=null;
  if(key==='rule.closure.confirm') body=`${weekdays[a.weekday] || a.weekday || '计划当天'}闭馆，按当前安排可能无法入内。${choice}`;
  else if(key==='rule.closure.reason') {
    const bilingual=(c.poi?.operating_rules?.closure_rules || []).find(rule=>a.reason && rule.reason_en===a.reason)?.reason_zh;
    const reason=bilingual || (/[\u4e00-\u9fff]/.test(a.reason || '') ? a.reason : '计划当天可能暂停开放，请核对官方公告');
    body=`有暂停开放提醒：${reason}。${choice}`;
    if(!bilingual && a.reason && !/[\u4e00-\u9fff]/.test(a.reason)) sourceNote=a.reason;
  }
  else if(key==='rule.closure.data_unknown' || key==='rule.closure.data_unverified') {
    group='verify';body='开放与闭馆信息尚未核实，暂时无法判断当天能否入内。出发前请核对景点官网或官方公告。';
  } else if(key==='rule.lightup.too_early') {
    body=`${time ? `预计${time}到达` : '计划到达时间偏早'}；建议${a.T_light || '傍晚'}以后到达，方便观看夜景。`;
    if(a.light_start) body+=` 亮灯时段：${a.light_start}${a.light_close ? '–'+a.light_close : '起'}。`;
  } else if(key==='rule.lightup.too_late') body=`${time ? `预计${time}到达` : '到达时间偏晚'}；亮灯${a.window_close || '当晚'}结束，可能看不到夜景。建议提前前往或调整日期。`;
  else if(key==='rule.spread.long_transit') body=`${a.from_name_zh && a.to_name_zh ? a.from_name_zh+' → '+a.to_name_zh+'：' : '相邻景点之间'}交通约${a.duration_minutes ?? '待确认'}分钟${a.distance_km!=null ? `，直线距离约${a.distance_km}公里` : ''}。可以将其中一个景点换到其他天，减少往返。`;
  else if(key==='rule.homogeneous.banner') body=`这一天有${a.count ?? '多个'}个${a.category_zh || (/[\u4e00-\u9fff]/.test(a.category || '') ? a.category : '同类')}景点。可以搭配其他类别，让安排更丰富。`;
  if(notice.severity==='hard') {
    group=notice.outcome==='confirmed_proceed' ? 'suggest' : 'needs';
    if(notice.outcome==='confirmed_proceed') body+=' 你已选择保留，闭馆风险仍然存在。';
  }
  if((key || '').startsWith('rule.lightup.') && (!c.day || !c.name)) body+=' 请重新检查行程，确认这条提醒对应的日期和景点。';
  return {title,body,group,context:c,sourceNote};
}
function reminderText(notice) {const m=reminderModel(notice);return `${m.title}：${m.body}`;}

function openReminderDay(dayIndex) {
  const node=typeof dayCards!=='undefined' ? dayCards.nodes.get(dayIndex) : null;
  if(!node) return;
  node.card.open=true;dayCards.open.add(dayIndex);setCurrentDay(dayIndex);
  node.card.scrollIntoView({block:'start',behavior:'auto'});
  node.card.querySelector('.day-summary')?.focus({preventScroll:true});
}

function reminderCard(notice) {
  const m=reminderModel(notice),row=element('article',`reminder-card${m.group==='needs' ? ' warning' : ''}`);
  row.append(element('h4','',m.title),element('p','',m.body));
  if(m.sourceNote) {
    const note=element('p','',m.sourceNote);note.setAttribute('data-i18n-ignore','');
    const source=element('details','reminder-source');source.append(element('summary','','查看原始备注'),note);row.append(source);
  }
  const actions=element('div','reminder-actions');
  if(notice.severity==='hard' && notice.outcome!=='confirmed_proceed') {
    const id=notice.message_args?.notice_id;
    if(id) actions.append(actionButton('仍然保留',async()=>{
      const data=await api(`/api/trips/${state.trip.trip_id}/conflicts/${encodeURIComponent(id)}/confirm`,{method:'POST',body:{decision:'proceed_anyway'}});
      state.trip=data.trip;await evaluateTrip();
    }),actionButton('移除此景点',async()=>{
      const [,dayIndex,poiId]=id.split(':');
      const data=await api(`/api/trips/${state.trip.trip_id}/days/${dayIndex}/stops/${encodeURIComponent(poiId)}`,{method:'DELETE'});
      state.trip=data.trip;await afterTripEdit('remove_stop');
    }));
  }
  if(m.context.day) {
    const button=element('button','secondary',m.group==='verify' ? '查看当天安排' : '调整当天安排');button.type='button';
    button.addEventListener('click',()=>openReminderDay(m.context.dayIndex));actions.append(button);
  }
  if(actions.children.length) row.append(actions);
  return row;
}

function renderTripReminders(list,result,rulesUp) {
  if(!rulesUp) {list.append(element('p','warning','提醒服务暂未连接，尚不能检查景点开放与夜景时间。服务恢复后点击“重新检查”。'));return;}
  if(result.error) {list.append(element('p','warning','本次检查未完成，请稍后重新检查。'));return;}
  if(!result.notices) {list.append(element('p','hint','还没有检查结果。点击“重新检查”，查看安排是否需要调整。'));return;}
  const all=[...(result.notices || []),...(result.overflow_notices || [])];
  const seen=new Set(),groups={needs:[],suggest:[],verify:[]};
  for(const notice of all) {
    const identity=JSON.stringify([notice.message_key,notice.message_args,notice.outcome]);
    if(seen.has(identity)) continue;seen.add(identity);groups[reminderModel(notice).group].push(notice);
  }
  const missing=(state.trip.days || []).map(day=>({day,count:day.ordered_stops.filter(s=>s.transit_from_previous?.duration_seconds==null).length})).filter(d=>d.count);
  const incomplete=missing.length>0 || result.skipped_rules?.length>0 || (result.overflow || 0)>(result.overflow_notices || []).length;
  const summary=element('div',`reminder-summary${groups.needs.length ? ' reminder-attention' : ''}`);
  summary.append(element('strong','',groups.needs.length ? `${groups.needs.length}处安排需要你处理` : incomplete ? '还不能完整判断行程是否合适' : groups.verify.length ? `有${groups.verify.length}处开放信息需要出发前核实` : '已完成检查，未发现需要处理的闭馆冲突'),
    element('p','hint',all.length || incomplete ? `${groups.suggest.length}条安排建议 · ${groups.verify.length}处开放信息待核实。${incomplete ? '补齐下方信息后再检查。' : '请查看下方提醒。'}` : '修改景点或出发时间后会自动再检查。'));
  list.append(summary);
  for(const [key,title,description] of [['needs','需要处理','这些安排可能无法按计划完成。'],['suggest','安排建议','可以按自己的旅行偏好调整。'],['verify','出发前核实','资料尚未确认，不代表景点一定闭馆。']]) {
    if(!groups[key].length) continue;
    const group=element('section',`reminder-group reminder-${key}`);
    group.append(element('h3','',`${title}（${groups[key].length}）`),element('p','hint',description));
    for(const notice of groups[key]) group.append(reminderCard(notice));list.append(group);
  }
  if(incomplete) {
    const pending=element('section','reminder-group reminder-pending');pending.append(element('h3','','检查还缺哪些信息'));
    for(const {day,count} of missing) {
      const row=element('div','reminder-card');row.append(element('p','',`第${day.day_index}天（${day.date}）还有${count}段交通时间未确定，暂时算不出完整的到达时间。`));
      const button=actionButton(`计算第${day.day_index}天交通`,async()=>{openReminderDay(day.day_index);await computeDayRoutes(day.day_index);});
      button.disabled=!engineReady('route_adapter');row.append(button);pending.append(row);
    }
    const checks={rule_01_closure:'闭馆日期',rule_02_lightup:'夜景到达时间',rule_03_spread:'景点间的交通与距离',rule_04_homogeneous:'景点类别搭配'};
    const known=new Set();
    for(const skip of result.skipped_rules || []) {
      if(skip.reason==='missing_route_duration' && missing.length) continue;
      const name=checks[skip.rule_id] || '部分行程安排';
      const text=`${name}：${skip.reason==='no_match' ? '没有适用于出行日期的资料' : skip.reason==='missing_route_duration' ? '缺少交通耗时' : '所需资料还不完整'}，暂时无法给出结论。`;
      if(!known.has(text)) {known.add(text);pending.append(element('p','hint',text));}
    }
    if((result.overflow || 0)>(result.overflow_notices || []).length) pending.append(element('p','hint','部分提醒尚未载入，请重新检查。'));
    list.append(pending);
  }
}
