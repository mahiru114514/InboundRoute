/* 起终点及恢复默认预览由 core/trip_points.py 统一派生。 */
function resolveDayPoints(trip) {
  return trip.resolved_day_points || {};
}

function dayPointIdentity(point) {
  const c=point?.coordinate;
  return point ? JSON.stringify([point.type,point.poi_id || null,point.name_zh,point.name_en,c?.lat,c?.lng,c?.crs,c?.precision_m ?? null]) : '';
}

function dayNeedsTransport(trip,day) {
  if(day.ordered_stops?.length) return true;
  const points=resolveDayPoints(trip)[day.day_index];
  return !!(points?.start && points?.end && dayPointIdentity(points.start)!==dayPointIdentity(points.end));
}

function dayPointOptions(trip,field) {
  const options=[];
  const coordinate=anchor=>anchor.coordinate || (Number.isFinite(anchor.lat) && Number.isFinite(anchor.lng)
    ? {lat:anchor.lat,lng:anchor.lng,crs:'WGS84'} : null);
  const add=(key,anchor,group,extra='')=>{
    if(!anchor?.coordinate) return;
    options.push({key,anchor,group,search:[anchor.name_zh,anchor.name_en,anchor.name_pinyin,extra].join(' ').toLowerCase()});
  };
  for(const hotel of (typeof anchors === 'function' ? anchors('hotels') : [...(state.anchors?.hotels || []),...(state.savedHotels || [])])) add('hotel:'+hotel.id,{type:'hotel',name_zh:hotel.name_zh,name_en:hotel.name_en,
    ...(hotel.name_pinyin ? {name_pinyin:hotel.name_pinyin} : {}),poi_id:hotel.poi_id || null,coordinate:coordinate(hotel)},'酒店',(hotel.aliases || []).join(' '));
  const currentHotel={...trip.anchor_hotel,type:'hotel'};
  if(currentHotel.coordinate && !options.some(o=>dayPointIdentity(o.anchor)===dayPointIdentity(currentHotel)))
    add('current-hotel',currentHotel,'当前住宿');
  for(const hub of state.anchors?.hubs || []) add('hub:'+hub.id,{type:field==='start_anchor' ? 'arrival_anchor' : 'departure_anchor',
    name_zh:hub.name_zh,name_en:hub.name_en,coordinate:coordinate(hub)},'口岸',[hub.name_pinyin,...(hub.aliases || [])].join(' '));
  for(const poi of state.pois || []) add('poi:'+poi.poi_id,{type:'poi',poi_id:poi.poi_id,name_zh:poi.names['zh-Hans'],name_en:poi.names.en,
    coordinate:poi.coordinate},'景点',[poi.romanization?.pinyin,poi.romanization?.pinyin_plain,...(poi.search_aliases || [])].join(' '));
  for(const day of trip.days) for(const saved of [day.start_anchor,day.end_anchor]) {
    if(saved && !options.some(o=>dayPointIdentity(o.anchor)===dayPointIdentity(saved))) add('saved:'+options.length,saved,'已保存地点');
  }
  return options;
}

function renderDayPoints(trip,day,container) {
  const points=resolveDayPoints(trip);
  const disclosure=element('details','day-point-disclosure');disclosure.open=false;
  disclosure.append(element('summary','','调整起终点'));
  const box=element('div','day-point-settings');
  for(const field of ['start_anchor','end_anchor']) {
    const title=field==='start_anchor' ? '起始点' : '终止点';
    const setting=element('div','day-point-setting');
    const label=element('label','',title);
    const search=element('input','day-point-search');search.type='search';search.placeholder='搜索酒店、口岸或景点';
    search.setAttribute('aria-label',`Day ${day.day_index} ${title}搜索`);
    const select=element('select','day-point-select');select.dataset.field=field;
    select.setAttribute('aria-label',`Day ${day.day_index} ${title}`);label.append(select);
    const options=dayPointOptions(trip,field);
    const saved=day[field] ? options.find(o=>dayPointIdentity(o.anchor)===dayPointIdentity(day[field]))?.key || '' : '';
    const populate=()=>{
      const previous=select.value;
      select.replaceChildren();
      const actual=trip.default_day_points?.[day.day_index]?.[field==='start_anchor'?'start':'end'];
      const defaultOption=element('option','',`自动 · ${actual?.name_zh || '未设置'}`);defaultOption.value='';select.append(defaultOption);
      const keyword=search.value.trim().toLowerCase();
      const matches=options.filter(o=>!keyword || o.search.includes(keyword) || o.search.replace(/\s+/g,'').includes(keyword));
      const savedChoice=options.find(o=>o.key===saved);
      if(savedChoice && !matches.includes(savedChoice)) matches.unshift(savedChoice);
      for(const choice of matches) {const option=element('option','',`${choice.group} · ${choice.anchor.name_zh}`);option.value=choice.key;select.append(option);}
      if(!matches.length && keyword) {const option=element('option','','没有匹配地点，请换关键词');option.disabled=true;select.append(option);}
      select.value=matches.some(o=>o.key===previous) ? previous : matches.some(o=>o.key===saved) ? saved : '';
    };
    select.value=saved;search.value='';populate();
    search.addEventListener('input',populate);
    select.addEventListener('change',()=>{
      if(select.value===saved) return;
      if(state.busy) {select.value=saved;notify('正在处理上一项修改，请稍后再试。');return;}
      const selected=options.find(o=>o.key===select.value)?.anchor || null;
      flowAction(async()=>{try {await saveDayAnchor(day.day_index,field,selected);} catch(error) {select.value=saved;throw error;}});
    });
    setting.append(label,search);box.append(setting);
  }
  disclosure.append(box);
  const previous=points[day.day_index-1]?.end;
  const start=points[day.day_index]?.start;
  if(previous && start && dayPointIdentity(previous)!==dayPointIdentity(start))
    disclosure.append(element('p','warning',`前一天结束在${previous.name_zh}，当天从${start.name_zh}出发，请确认住宿或接驳安排。`));
  disclosure.append(element('p','hint','换酒店时选择新的终止点，后续日期默认从那里出发；选择“自动”可恢复默认。修改后请重新计算受影响日期的交通。'));
  container.append(disclosure);
}


function renderAnchorStopPicker(trip,day,container) {
  const disclosure=element('details','anchor-stop-disclosure');disclosure.open=false;
  disclosure.append(element('summary','','添加住宿 / 口岸'));
  const box=element('div','anchor-stop-picker');
  const search=element('input','anchor-stop-search');search.type='search';search.value='';search.placeholder='搜索酒店或口岸';
  search.setAttribute('aria-label','搜索要添加的住宿或口岸');
  const select=element('select','day-point-select');
  select.setAttribute('aria-label','Day '+day.day_index+' 添加住宿或口岸');
  const choices=dayPointOptions(trip,'start_anchor').filter(o=>o.anchor.type!=='poi');
  for(const kind of ['arrival_anchor','departure_anchor']) {
    const saved=trip[kind==='arrival_anchor'?'anchor_arrival':'anchor_departure'];
    if(saved?.coordinate) choices.push({key:kind,group:'行程口岸',search:saved.location_name.toLowerCase(),anchor:{type:kind,
      name_zh:saved.location_name,name_en:saved.location_name,coordinate:saved.coordinate}});
  }
  const dwell=element('input','anchor-dwell');dwell.type='number';dwell.min=0;dwell.max=720;dwell.value=60;
  dwell.setAttribute('aria-label','停留分钟数');
  const label=element('label','','停留（分钟）');label.append(dwell);
  const position=element('select','anchor-position');position.setAttribute('aria-label','加入位置');
  for(let i=1;i<=day.ordered_stops.length+1;i++) {const option=element('option','',i===day.ordered_stops.length+1?'加入末尾':'插入第 '+i+' 项之前');option.value=String(i);position.append(option);}
  position.value=String(day.ordered_stops.length+1);
  const purposeLabel=element('label','hotel-stay-setting','住宿用途');
  const purpose=element('select','hotel-stay-kind');purpose.setAttribute('aria-label','住宿用途');
  for(const [value,text] of [['rest','休息'],['overnight','过夜住宿']]) {const option=element('option','',text);option.value=value;purpose.append(option);}purpose.value='rest';purposeLabel.append(purpose);
  const button=element('button','secondary','添加到行程');button.type='button';
  const syncPurpose=()=>{const hotel=choices.find(c=>c.key===select.value)?.anchor.type==='hotel';purposeLabel.hidden=!hotel;};
  const populate=()=>{
    const previous=select.value,keyword=search.value.trim().toLowerCase();
    const matched=choices.filter(choice=>!keyword || (choice.search || '').includes(keyword)
      || (choice.search || '').replace(/\s+/g,'').includes(keyword));
    select.replaceChildren();
    const prompt=element('option','',matched.length?'请选择住宿或口岸':'没有匹配地点，请换关键词');prompt.value='';select.append(prompt);
    for(const choice of matched) {const option=element('option','',choice.group+' · '+choice.anchor.name_zh);option.value=choice.key;select.append(option);}
    select.value=matched.some(c=>c.key===previous)?previous:'';select.disabled=!matched.length;button.disabled=!matched.length;syncPurpose();
  };
  select.value=choices[0]?.key || '';populate();
  search.addEventListener('input',populate);select.addEventListener('change',syncPurpose);
  button.addEventListener('click',()=>flowAction(async()=>{
    const selected=choices.find(c=>c.key===select.value)?.anchor;
    if(!selected) throw new Error('请先选择要添加的住宿或口岸');
    const minutes=Number(dwell.value);
    if(!Number.isInteger(minutes) || minutes<0 || minutes>720) throw new Error('停留时长须为 0~720 分钟');
    await addAnchorStop(day.day_index,selected,Number(position.value),minutes,selected.type==='hotel'?purpose.value:null);
  }));
  box.append(search,select,label,position,purposeLabel,button);disclosure.append(box);container.append(disclosure);
}
