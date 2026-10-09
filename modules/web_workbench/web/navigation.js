/* 当前方案详情与高德 URI；只有明确点击链接才打开外部地图。 */
const NAVIGATION_MODES={transit:'bus',taxi:'car',walk:'walk',bike:'ride'};
const NAVIGATION_LABELS={transit:'公共交通',taxi:'驾车（打车方案）',walk:'步行',bike:'骑行'};

function navigationPoint(point) {
  if(!point || !Number.isFinite(point.lat) || !Number.isFinite(point.lng)
    || Math.abs(point.lat)>90 || Math.abs(point.lng)>180) return null;
  if(point.crs==='GCJ-02') return {lat:point.lat,lng:point.lng};
  if(point.crs==='WGS84') return window.IRMap?.gcj02FromWgs84(point) || null;
  if(point.crs==='BD-09') {
    const x=point.lng-.0065,y=point.lat-.006,xpi=Math.PI*3000/180;
    const z=Math.sqrt(x*x+y*y)-.00002*Math.sin(y*xpi),theta=Math.atan2(y,x)-.000003*Math.cos(x*xpi);
    return {lng:z*Math.cos(theta),lat:z*Math.sin(theta)};
  }
  return null;
}

function navigationEndpoints(trip,dayIndex,index) {
  const day=trip?.days?.find(d=>d.day_index===dayIndex);
  if(!day || !Number.isInteger(index) || index<0 || index>day.ordered_stops.length) return null;
  const points=resolveDayPoints(trip)[dayIndex];
  const poi=stop=>{
    if(stop?.coordinate) return {type:stop.stop_type,poi_id:stop.poi_id,name_zh:stop.name_zh,coordinate:stop.coordinate};
    const record=state.pois.find(p=>p.poi_id===stop?.poi_id);
    return record ? {poi_id:record.poi_id,name_zh:record.names['zh-Hans'],coordinate:record.coordinate} : null;
  };
  return {start:index===0 ? points?.start : poi(day.ordered_stops[index-1]),
    end:index===day.ordered_stops.length ? points?.end : poi(day.ordered_stops[index])};
}

function routeNavigation(trip,dayIndex,index,route) {
  const unavailable=reason=>({nativeURL:null,webURL:null,reason});
  if(route?.data_source==='mock') return unavailable('演示方案不能用于导航，请先计算真实路线。');
  if(!route || !['amap','tencent','baidu','api'].includes(route.data_source)
    || !Number.isFinite(route.duration_seconds) || route.duration_seconds<0)
    return unavailable('尚未选定可用的真实方案，请先计算并选择路线。');
  const mode=NAVIGATION_MODES[route.mode];
  if(typeof mode!=='string') return unavailable('此交通方式暂不支持高德导航。');
  const endpoints=navigationEndpoints(trip,dayIndex,index);
  if(!endpoints) return unavailable('当前区间已变化，请重新计算交通。');
  const start=endpoints?.start;
  let destination=endpoints?.end,dropOff=false;
  if(route.mode==='taxi' && navigationPoint(route.drop_off?.point)) {
    destination={coordinate:route.drop_off.point,name_zh:route.drop_off.desc_zh || destination?.name_zh};dropOff=true;
  }
  const from=navigationPoint(start?.coordinate),to=navigationPoint(destination?.coordinate);
  if(!from || !to) return unavailable('起终点缺少有效坐标，请重新选择地点并计算交通。');
  if(route.to?.poi_id && endpoints?.end?.poi_id && route.to.poi_id!==endpoints?.end.poi_id)
    return unavailable('方案终点与当前景点不一致，请重新计算交通。');
  const url=new URL('https://uri.amap.com/navigation');
  url.searchParams.set('from',`${from.lng.toFixed(6)},${from.lat.toFixed(6)},${start.name_zh || '起点'}`);
  url.searchParams.set('to',`${to.lng.toFixed(6)},${to.lat.toFixed(6)},${destination.name_zh || '终点'}`);
  url.searchParams.set('mode',mode);url.searchParams.set('policy','0');url.searchParams.set('src','InboundRoute');
  url.searchParams.set('callnative','1');const nativeURL=url.href;
  url.searchParams.set('callnative','0');
  return {nativeURL,webURL:url.href,start,destination,dropOff,mode,label:NAVIGATION_LABELS[route.mode]};
}

function parseRoutePolyline(value) {
  if(typeof value!=='string') return [];
  const pieces=value.split(';');if(pieces.length<2 || pieces.length>10000) return [];
  const points=[];
  for(const piece of pieces) {
    const pair=piece.split(',');if(pair.length!==2 || pair.some(p=>!p.trim())) return [];
    const [lng,lat]=pair.map(Number);
    if(!Number.isFinite(lng) || !Number.isFinite(lat) || Math.abs(lng)>180 || Math.abs(lat)>90) return [];
    points.push({lng,lat});
  }
  return points;
}

function routeInstructions(route) {
  return (route.segments || []).map(segment=>{
    const duration=Number.isFinite(segment.duration_seconds) ? `约${Math.ceil(segment.duration_seconds/60)}分钟` : '';
    if(segment.kind==='walk') return ['步行',Number.isFinite(segment.distance_meters) ? `${segment.distance_meters}米` : '',duration,
      segment.walk_note_zh || segment.walk_note_en].filter(Boolean).join(' · ');
    if(segment.kind==='ride') {
      const board=[segment.board?.station_name_zh,segment.board?.access_name_zh].filter(Boolean).join(' ');
      const alight=[segment.alight?.station_name_zh,segment.alight?.access_name_zh].filter(Boolean).join(' ');
      return [segment.line?.name_zh || segment.line?.name_en || '公共交通',
        board ? `${board}上车` : '',alight ? `${alight}下车` : '',segment.direction?.name_zh,
        Number.isFinite(segment.stops) ? `${segment.stops}站` : '',duration].filter(Boolean).join(' · ');
    }
    if(segment.kind==='transfer') return ['换乘',segment.transfer?.note_zh || segment.transfer?.note_en,
      Number.isFinite(segment.transfer?.walking_distance_meters) ? `步行${segment.transfer.walking_distance_meters}米` : '',duration].filter(Boolean).join(' · ');
    return '';
  }).filter(Boolean);
}

function routeShapePreview(points) {
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 320 150');svg.setAttribute('role','img');svg.setAttribute('aria-label','已选路线的线路形状预览，无底图与实时定位');
  svg.classList.add('route-shape');
  const cosine=Math.cos(points.reduce((s,p)=>s+p.lat,0)/points.length*Math.PI/180);
  const xs=points.map(p=>p.lng*cosine),ys=points.map(p=>p.lat);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const scale=Math.min(280/Math.max(maxX-minX,1e-8),110/Math.max(maxY-minY,1e-8));
  const coords=points.map((p,i)=>[160+(xs[i]-(minX+maxX)/2)*scale,75-(ys[i]-(minY+maxY)/2)*scale]);
  const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('points',coords.map(p=>p.join(',')).join(' '));svg.append(line);
  for(const [position,label] of [[0,'起始点'],[coords.length-1,'终止点']]) {
    const [x,y]=coords[position],circle=document.createElementNS(svg.namespaceURI,'circle');
    circle.setAttribute('cx',x);circle.setAttribute('cy',y);circle.setAttribute('r','5');svg.append(circle);
    const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',x);text.setAttribute('y',y-10);text.setAttribute('text-anchor',x<160?'start':'end');text.textContent=label;svg.append(text);
  }
  return svg;
}

function renderRouteNavigation(card,dayIndex,index,route) {
  const trip=state.trip,day=trip.days.find(d=>d.day_index===dayIndex);
  const active=day?.ordered_stops[index]?.transit_from_previous || route;
  const nav=routeNavigation(trip,dayIndex,index,active);
  const details=element('details','route-details');
  details.append(element('summary','',`查看已选路线 · ${NAVIGATION_LABELS[active.mode] || active.mode}`));
  const content=element('div','route-detail-content');
  const points=parseRoutePolyline(active.polyline);
  if(points.length && active.data_source!=='mock' && active.duration_seconds!=null) {
    content.append(element('p','hint','线路形状预览 · 无底图与实时定位'),routeShapePreview(points));
  } else content.append(element('p','hint','暂无完整线路轨迹；导航时在高德查看实时路线。'));
  const instructions=routeInstructions(active);
  const list=element('ol','route-instructions');
  for(const instruction of instructions) list.append(element('li','',instruction));
  if(instructions.length) content.append(list);
  else content.append(element('p','hint',active.mode==='taxi' ? '当前为打车方案，导航入口打开驾车路线，不提供叫车服务。' : '暂未提供详细路段说明，请在高德查看。'));
  details.append(content);card.append(details);
  if(!nav.nativeURL) {card.append(element('p','hint navigation-unavailable',nav.reason));return;}
  const actions=element('div','navigation-actions');
  for(const [label,url] of [['开始导航（高德）',nav.nativeURL],['高德网页版',nav.webURL]]) {
    const link=element('a','navigation-link',label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';
    link.addEventListener('click',event=>{
      const current=state.trip?.days.find(d=>d.day_index===dayIndex);
      const selected=current?.ordered_stops[index]?.transit_from_previous || (index===current?.ordered_stops.length ? current.end_transit : null) || flow.routes[dayIndex]?.[index];
      const fresh=state.trip?.trip_id===trip.trip_id && selected ? routeNavigation(state.trip,dayIndex,index,selected) : null;
      if(state.busy || fresh?.nativeURL!==nav.nativeURL) {event.preventDefault();notify('行程正在修改或方案已变化，请等待保存完成后使用新的导航入口。',true);}
    });
    actions.append(link);
  }
  card.append(actions,element('p','hint navigation-note',`按计划起点出发 · ${nav.label}。手机尝试打开高德App；无法打开时可使用网页版。高德会重新规划，具体线路可能不同。`));
  if(nav.dropOff) card.append(element('p','hint',`驾车导航到落客点：${nav.destination.name_zh}。下车后请核实步行入口。`));
}
