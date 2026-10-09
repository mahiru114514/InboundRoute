/* 隔离浏览器验收：所有 API 在本进程内存响应，禁止真实网络及用户行程写入。
 * Run: NODE_PATH=<bundled node_modules> node tools/verify_soft_utility.cjs
 */
"use strict";
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const vm=require('node:vm');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const web = path.join(root, 'modules/web_workbench/web');
const pointContext={};vm.createContext(pointContext);vm.runInContext(fs.readFileSync(path.join(web,'day_points.js'),'utf8'),pointContext);
const output = path.join(root, 'docs/验收截图');
const pois = JSON.parse(execFileSync('python', ['-X','utf8','-c',
  'import json; from modules.trip_engine.poi_seed import POIS; print(json.dumps(POIS,ensure_ascii=False))'], {cwd:root,encoding:'utf8'}));
const anchors = JSON.parse(fs.readFileSync(path.join(root,'modules/trip_engine/data/anchors.json'),'utf8'));
const calls = [], errors = [], checks = [];
let trip = null, simulatePartial = false, simulateStartFailure = false, simulateEndpointFailure=false, simulateRealRoutes=false;
function check(name, value) { assert.ok(value, name); checks.push(name); console.log('PASS', name); }
const stamp = 1791820800;
function createTrip(body) {
  return {trip_id:'visual_demo',version:1,status:'draft',
    user_profile:{...body.user_profile,walking_speed_factor:1,party_walk_multiplier:1,prefer_taxi:false},
    anchor_arrival:{...body.anchor_arrival,activity_start_at:body.anchor_arrival.at+7200},
    anchor_hotel:body.anchor_hotel,anchor_departure:body.anchor_departure,
    days:Array.from({length:body.duration_days},(_,i)=>({day_index:i+1,date:`2026-10-${12+i}`,
      day_status:i===0?'arrival_only':'empty',daily_start_local:body.daily_start_local||'09:00',poi_cap:4,ordered_stops:[]}))};
}
function evaluation() {
  for(const day of trip.days) {
    const configured=Date.parse(day.date+'T'+day.daily_start_local+':00+08:00')/1000;
    let at=day.day_index===1 ? Math.max(trip.anchor_arrival.activity_start_at,configured) : configured, blocked=false;
    for(const stop of day.ordered_stops) {
      if(stop.transit_from_previous?.duration_seconds == null) blocked=true;
      if(blocked) {stop.arrival_at=null;stop.departure_at=null;continue;}
      stop.arrival_at=at+stop.transit_from_previous.duration_seconds;
      stop.departure_at=stop.arrival_at+stop.planned_dwell_minutes*60;at=stop.departure_at;
    }
  }
  return {trip,notices:[],timeline:[],skipped_rules:['rule_03_demo']};
}
function api(url, method, body) {
  calls.push({url,method,body});
  if(url==='/api/session') return {token:'isolated-visual-test',map:{ready:false,provider:'none',hint:'隔离验收使用示意地图'}};
  if(url==='/api/services') return {services:['trip_engine','rules_engine','route_adapter','offline_kit'].map(module_id=>({module_id,ready:true,health:'ok',purpose:'隔离验收',detail:'演示响应'})),ready:{trip_engine:true,rules_engine:true,route_adapter:true,offline_kit:true}};
  if(url==='/api/pois') return {pois};
  if(url==='/api/anchors') return anchors;
  if(url==='/api/trips:validate') return {valid:true,duration_days:body.duration_days};
  if(url==='/api/trips' && method==='GET') return {trips:trip?[{trip_id:trip.trip_id,version:trip.version,start_date:'2026-10-12',duration_days:trip.days.length}]:[]};
  if(url==='/api/trips' && method==='POST') {trip=createTrip(body);return trip;}
  if(url.endsWith('/rules:precheck')) return {would_block:false,hard_conflicts:[],notices:[],timeline:[],skipped_rules:[]};
  if(url.endsWith('/rules:evaluate')) return evaluation();
  const add=url.match(/\/days\/(\d+)\/stops$/);
  if(add && method==='POST') {
    const day=trip.days[Number(add[1])-1];day.ordered_stops.push({poi_id:body.poi_id,stop_order:day.ordered_stops.length+1,
      planned_dwell_minutes:body.planned_dwell_minutes||90,locked:false,arrival_at:null,departure_at:null,transit_from_previous:null,rule_notices:[]});
    if(day.day_status!=='arrival_only') day.day_status='partial';trip.version++;return {trip,pacing_warning:null};
  }
  const route=url.match(/\/days\/(\d+)\/routes:compute$/);
  if(route) {
    const day=trip.days[Number(route[1])-1],index=body.segment_index;
    const points=pointContext.resolveDayPoints(trip)[day.day_index];
    const name=id=>pois.find(p=>p.poi_id===id)?.names['zh-Hans'];
    const selectedMode=body.modes?.[0]||'transit';
    const variants=[{mode:'transit',duration_seconds:simulatePartial&&index===1?null:1200,distance_meters:3100,cost:{min:4,max:4}},
      {mode:'taxi',duration_seconds:720,distance_meters:3600,cost:{min:20,max:28}},
      {mode:'walk',duration_seconds:2700,distance_meters:3000,cost:null}];
    const selected=variants.find(v=>v.mode===selectedMode);
    const fixtureSegments=selectedMode==='transit' ? [
      {kind:'walk',duration_seconds:180,distance_meters:200,walk_note_zh:'隔离验收：步行到测试车站'},
      {kind:'ride',duration_seconds:1020,line:{name_zh:'测试地铁2号线'},board:{station_name_zh:'测试起点站'},alight:{station_name_zh:'测试终点站'},stops:3}
    ] : selectedMode==='walk' ? [{kind:'walk',duration_seconds:2700,distance_meters:3000,walk_note_zh:'隔离验收：沿测试道路步行'}] : [];
    return {routes:[{...selected,data_source:simulateRealRoutes?'amap':'mock',has_long_transfer:false,partial:selected.duration_seconds==null,
      segments:simulateRealRoutes?fixtureSegments:[],polyline:simulateRealRoutes?'121.47,31.23;121.475,31.235;121.48,31.232':null,
      drop_off:simulateRealRoutes&&selectedMode==='taxi'&&index<day.ordered_stops.length ? {point:pois.find(p=>p.poi_id===day.ordered_stops[index].poi_id).coordinate,desc_zh:'隔离测试落客点'} : null,
      from:{name_zh:index===0?points.start.name_zh:name(day.ordered_stops[index-1].poi_id)},
      to:{name_zh:index<day.ordered_stops.length?name(day.ordered_stops[index].poi_id):points.end.name_zh},variants:body.modes ? variants.filter(v=>body.modes.includes(v.mode)) : variants}]};
  }
  if(url.endsWith('/offline-package')) return {trip_version:trip.version,generated_at:Math.floor(Date.now()/1000),payload:{days:trip.days.map(day=>({day_index:day.day_index,date:day.date,
    start_anchor:pointContext.resolveDayPoints(trip)[day.day_index].start,end_anchor:pointContext.resolveDayPoints(trip)[day.day_index].end,
    stops:day.ordered_stops.map(stop=>({...stop,name_zh:pois.find(p=>p.poi_id===stop.poi_id).names['zh-Hans'],data_source:'mock',ask_cards:[{template_key:'poi_arrival',args:{poi_name_zh:pois.find(p=>p.poi_id===stop.poi_id).names['zh-Hans'],poi_name_en:pois.find(p=>p.poi_id===stop.poi_id).names.en}}]}))}))}};
  if(/^\/api\/trips\/[^/]+$/.test(url)) {
    if(method==='PATCH') {
      if(body.days) {
        const before=pointContext.resolveDayPoints(trip);
        for(const edit of body.days) {
        const day=trip.days.find(d=>d.day_index===edit.day_index);
        if(edit.daily_start_local && simulateStartFailure) {const failure=new Error('版本冲突，请重试出发时刻修改');failure.expected=true;throw failure;}
        if(simulateEndpointFailure && ('start_anchor' in edit || 'end_anchor' in edit)) {const failure=new Error('地点保存失败，请重试');failure.expected=true;throw failure;}
        for(const field of ['start_anchor','end_anchor']) if(field in edit) day[field]=edit[field];
        if(edit.daily_start_local) {day.daily_start_local=edit.daily_start_local;day.ordered_stops.forEach(stop=>Object.assign(stop,{arrival_at:null,departure_at:null,transit_from_previous:null}));}
        for(const change of edit.ordered_stops||[]) Object.assign(day.ordered_stops.find(s=>s.stop_order===change.stop_order),change);
      }
        const after=pointContext.resolveDayPoints(trip);
        for(const day of trip.days) if(JSON.stringify(before[day.day_index])!==JSON.stringify(after[day.day_index]))
          day.ordered_stops.forEach(stop=>Object.assign(stop,{arrival_at:null,departure_at:null,transit_from_previous:null}));
      }
      else {trip.user_profile={...trip.user_profile,...body.user_profile};trip.anchor_hotel=body.anchor_hotel;trip.anchor_departure=body.anchor_departure;}
      trip.version++;
    }
    return trip;
  }
  throw new Error(`Unimplemented isolated endpoint: ${method} ${url}`);
}
const {ASSETS} = require("./workbench_assets.cjs");
const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost').pathname;
  try {
    if(url.startsWith('/api/')) {
      let raw='';for await(const chunk of req) raw+=chunk;
      const data=api(url,req.method,raw?JSON.parse(raw):null);
      res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:true,data,meta:{}}));return;
    }
    if(!ASSETS[url]) {res.writeHead(404);res.end();return;}
    res.writeHead(200,{'Content-Type':ASSETS[url].mime});
    res.end(fs.readFileSync(path.resolve(web,ASSETS[url].file)));
  } catch(error) {if(!error.expected) errors.push(error.message);res.writeHead(error.expected?409:500);res.end(JSON.stringify({ok:false,error:{message:error.message}}));}
});
async function settled(page) {await page.waitForFunction(()=>!state.busy);}
async function layout(page,width) {
  await page.setViewportSize({width,height:900});
  await page.evaluate(()=>window.scrollTo(0,0));
  const result=await page.evaluate(()=>{
    const form=document.getElementById('setup-form').getBoundingClientRect();
    const departure=document.querySelector('.departure').getBoundingClientRect();
    return {viewport:innerWidth,doc:document.documentElement.scrollWidth,below:form.bottom>=departure.bottom,
      save:getComputedStyle(document.querySelector('.form-actions')).position,
      visibleLinks:[...document.querySelectorAll('.workspace-nav a')].filter(a=>getComputedStyle(a).display!=='none').length};
  });
  check(`${width}px 无横向溢出`,result.doc<=result.viewport);
  check(`${width}px 离境字段位于表单内`,result.below);
  check(`${width}px 保存操作位置`,result.save===(width<=600?'fixed':'static'));
  check(`${width}px 导航显隐同步`,result.visibleLinks===(trip?5:2));
}
function luminance(hex) {const rgb=hex.match(/[a-f\d]{2}/gi).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
(async()=>{
  let browser;
  try {
    fs.mkdirSync(output,{recursive:true});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const browserPath=process.env.VISUAL_BROWSER_PATH || ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe',chromium.executablePath()].find(p=>fs.existsSync(p));
    browser=await chromium.launch({headless:true,executablePath:browserPath});
    const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
    context.setDefaultTimeout(10000);
    const base=`http://127.0.0.1:${server.address().port}`;
    const externalRequests=[];
    await context.route('**/*',route=>{
      const requestURL=new URL(route.request().url());
      if(requestURL.origin!==base && requestURL.protocol!=='data:') externalRequests.push(requestURL.href);
      return requestURL.origin===base||requestURL.protocol==='data:'?route.continue():route.abort();
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.evaluate(()=>window.__workbenchBoot);
    check('景点种子加载',await page.locator('.poi').count()===pois.length);
    check('移除独立交通面板与导航',await page.locator('#route-panel, a[href="#route-panel"]').count()===0);
    check('全部交通计算入口位于行程概览',await page.locator('#trip-panel #compute-all-routes').count()===1);
    for(const width of [1440,768,390,320]) await layout(page,width);
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'soft-utility-mobile-initial.png'),fullPage:true});
    await page.screenshot({path:path.join(output,'soft-utility-mobile-overview.png')});
    await page.locator('#has-departure').check();
    for(const width of [1440,768,390,320]) await layout(page,width);
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#arrival-date').fill('2026-10-12');await page.locator('#arrival-time').fill('09:00');
    await page.locator('#arrival-hub').selectOption('hub_hongqiao_rail');await page.locator('#hotel').selectOption('hotel_peace');
    await page.locator('#departure-date').fill('2026-10-13');await page.locator('#departure-time').fill('20:00');
    await page.locator('#departure-hub').selectOption('hub_hongqiao_t2');
    await page.locator('#duration-days').fill('0');await page.locator('#save-trip').click();
    check('无效天数不发送创建请求',!calls.some(c=>c.url==='/api/trips'&&c.method==='POST'));
    await page.waitForFunction(()=>getComputedStyle(document.getElementById('duration-days')).borderTopColor==='rgb(129, 62, 56)');
    check('无效输入显示错误边界',await page.locator('#duration-days').evaluate(e=>e.matches(':user-invalid')));
    await page.locator('#duration-days').fill('2');await page.locator('#save-trip').click();
    await page.waitForFunction(()=>state.trip!==null&&!state.busy);
    check('保存新建行程',calls.some(c=>c.url==='/api/trips'&&c.method==='POST'));
    check('保存后历史说明同步',await page.locator('#history-hint').textContent().then(t=>t.includes('1 份已保存行程')));
    check('保存后设定默认收起', !await page.locator('#setup-disclosure').evaluate(e=>e.open));
    await page.locator('#setup-disclosure > summary').click();
    await page.locator('#pacing').selectOption('relaxed');await page.locator('#save-trip').click();await settled(page);
    check('再次保存更新已有行程',calls.some(c=>c.method==='PATCH'&&c.body?.user_profile?.pacing==='relaxed'));
    for (const query of ['上海博物馆东馆', 'dong fang lv zhou', 'Nanxiang Old Street']) {
      await page.locator('#poi-search').fill(query);
      check(`扩充POI可搜索：${query}`,await page.locator('.poi .link-button').count()===1);
    }
    await page.locator('#poi-search').fill('上海自然博物馆');
    await page.locator('.poi .link-button').click();
    check('新馆数据说明显示待核实与参考时长',await page.locator('#detail').innerText().then(t=>t.includes('资料存在冲突')&&t.includes('规划参考')));
    check('未知预约没有显示无需预约',!(await page.locator('#detail').innerText()).includes('无需预约'));
    await page.locator('#detail-close').click();
    await page.locator('#poi-search').fill('waitan');
    check('景点搜索筛选',await page.locator('.poi').count()===1);
    await page.locator('.poi .link-button').click();
    check('真实景点弹窗打开',await page.locator('#detail').evaluate(e=>e.open));
    await page.locator('#d-add').click();await settled(page);
    if(await page.locator('#detail').evaluate(e=>e.open)) await page.locator('#detail-close').click();
    await page.locator('#poi-search').fill('museum');await page.locator('.poi .link-button').first().click();
    await page.locator('#d-add').click();await settled(page);
    if(await page.locator('#detail').evaluate(e=>e.open)) await page.locator('#detail-close').click();
    await page.locator('#poi-search').fill('');
    check('景点加入行程',trip.days[0].ordered_stops.length===2);
    check('初始设定不再有统一出发时间',await page.locator('#setup-panel input[name="daily_start_local"]').count()===0);
    check('每天都有独立出发时间',await page.locator('.day-start-input').count()===2);
    check('不同日期使用不同卡片底色',await page.locator('.day-summary').evaluateAll(es=>new Set(es.map(e=>getComputedStyle(e).backgroundColor)).size===es.length));
    check('景点类别有不同推荐底色',await page.locator('.poi-art').evaluateAll(es=>new Set(es.map(e=>getComputedStyle(e).backgroundColor)).size>=3));
    check('每日卡默认折叠',await page.locator('.day').evaluateAll(es=>es.every(e=>!e.open)));
    check('封面显示未完成交通',await page.locator('.day').first().innerText().then(t=>t.includes('2 段交通待补')));
    check('折叠卡隐藏景点调整按钮',!await page.locator('.day .stop-controls').first().isVisible());
    const routeCallsBefore=calls.filter(c=>c.url.endsWith('/routes:compute')).length;
    await page.locator('.day-summary').first().focus();
    check('卡片键盘焦点在边界内可见',await page.locator('.day-summary').first().evaluate(e=>getComputedStyle(e).outlineStyle==='solid'&&parseFloat(getComputedStyle(e).outlineOffset)<0));
    await page.keyboard.press('Enter');
    await page.waitForFunction(()=>document.querySelector('.day').open);
    check('展开保留彩色摘要与白色详情',await page.locator('.day').first().evaluate(e=>getComputedStyle(e.querySelector('summary')).backgroundColor!==getComputedStyle(e).backgroundColor));
    check('键盘打开当天详情',await page.locator('.day .stop-controls').first().isVisible());
    check('展开不调用交通服务',calls.filter(c=>c.url.endsWith('/routes:compute')).length===routeCallsBefore);
    const firstStart=page.locator('.day-start-input').first();
    await firstStart.fill('12:30');await firstStart.dispatchEvent('change');await settled(page);
    check('首日可以推迟出发',trip.days[0].daily_start_local==='12:30');
    await page.locator('.day').nth(1).evaluate(e=>e.open=true);
    await page.locator('.day-start-input').nth(1).fill('10:30');
    await page.locator('.day-start-input').nth(1).dispatchEvent('change');await settled(page);
    check('不同日期分别保存不同时间',trip.days[0].daily_start_local==='12:30'&&trip.days[1].daily_start_local==='10:30');
    const callsBeforeEarly=calls.filter(c=>c.method==='PATCH'&&c.body?.days?.some(d=>d.daily_start_local)).length;
    await page.locator('.day-start-input').first().fill('08:00');
    await page.locator('.day-start-input').first().dispatchEvent('change');await settled(page);
    check('抵达日不能提前越过缓冲',trip.days[0].daily_start_local==='12:30'&&calls.filter(c=>c.method==='PATCH'&&c.body?.days?.some(d=>d.daily_start_local)).length===callsBeforeEarly&&await page.locator('.day-start-input').first().inputValue()==='12:30');
    simulateStartFailure=true;
    await page.locator('.day-start-input').nth(1).fill('11:30');
    await page.locator('.day-start-input').nth(1).dispatchEvent('change');await settled(page);
    check('保存失败恢复已保存出发时间',trip.days[1].daily_start_local==='10:30'&&await page.locator('.day-start-input').nth(1).inputValue()==='10:30');
    simulateStartFailure=false;

    await page.evaluate(()=>{state.trip=structuredClone(state.trip);renderTrip();renderFlow();});
    check('重绘恢复每日独立时间',await page.locator('.day-start-input').evaluateAll(es=>es.map(e=>e.value).join(',')==='12:30,10:30'));
    await page.locator('#setup-disclosure').evaluate(e=>e.open=true);
    await page.locator('#save-trip').click();await settled(page);
    check('保存全局设定不覆盖每日出发时间',trip.days[0].daily_start_local==='12:30'&&trip.days[1].daily_start_local==='10:30'&&!calls.filter(c=>c.method==='PATCH'&&c.body?.user_profile).at(-1).body.daily_start_local);
    await page.locator('#setup-disclosure').evaluate(e=>e.open=false);

    const focusButton=page.locator('.day .stop-controls button:not(:disabled)').first();await focusButton.focus();
    check('轮询测试前焦点确实进入卡内',await focusButton.evaluate(e=>document.activeElement===e));
    await page.evaluate(()=>window.__focusedCardNode=document.activeElement);
    await page.evaluate(()=>refreshServices());
    check('服务轮询不打断卡内焦点',await page.evaluate(()=>document.activeElement===window.__focusedCardNode));
    await page.locator('.day-traffic button').first().click();await settled(page);
    check('交通计算后保留展开状态',await page.locator('.day').first().evaluate(e=>e.open));
    check('当天直接显示交通方案',await page.locator('.day-routes .route-card').count()===3);
    check('封面显示时间轴生成',await page.locator('.day-summary').first().innerText().then(t=>t.includes('时间轴已生成')));
    await page.locator('.day-start-input').first().fill('13:00');
    await page.locator('.day-start-input').first().dispatchEvent('change');await settled(page);
    check('改变出发时间后清除旧交通并提示待补',trip.days[0].ordered_stops.every(s=>s.transit_from_previous===null)&&await page.locator('.day-summary').first().innerText().then(t=>t.includes('时间轴待补齐')));

    await page.locator('#compute-all-routes').click();await settled(page);
    check('交通计算含首日三区间及末日直接离境段',await page.locator('.day-routes .route-card').count()===4);
    check('演示数据明确标注',await page.locator('.day-routes').first().innerText().then(t=>t.includes('非真实导航')));
    simulatePartial=true;
    trip.days[0].ordered_stops[1].transit_from_previous=null;
    await page.evaluate(async()=>{state.trip=await api('/api/trips/visual_demo');renderTrip();renderFlow();});
    await page.locator('.day-traffic button').first().click();await settled(page);
    check('单方式失败在封面显示缺口',await page.locator('.day-summary').first().innerText().then(t=>t.includes('1 段交通待补')&&t.includes('时间轴待补齐')));
    const secondRoute=page.locator('.day-routes .route-card').nth(1);
    check('公交不可用在当天详情说明',await secondRoute.innerText().then(t=>t.includes('公共交通暂不可用')));
    check('不可用公交按钮禁用',await secondRoute.locator('button').first().isDisabled());
    await secondRoute.getByRole('button',{name:/步行/}).click();await settled(page);
    check('当天选择步行保存并生成时间轴',trip.days[0].ordered_stops[1].transit_from_previous.mode==='walk'&&await page.locator('.day-summary').first().innerText().then(t=>t.includes('时间轴已生成')&&!t.includes('段交通待补')));
    check('单模式响应后完整候选持久化',trip.days[0].ordered_stops[1].transit_from_previous.variants.length===3);
    simulatePartial=false;
    await page.evaluate(()=>{flow.routes={};renderTrip();renderFlow();});
    check('刷新结果后恢复保存的去程',await page.locator('.day-routes .route-card').count()===2);
    check('未保存的酒店返程明确待计算',await page.locator('.day-summary').first().innerText().then(t=>t.includes('返程待计算')));
    await page.locator('.day-routes .route-card').first().getByRole('button',{name:/步行/}).click();await settled(page);
    check('恢复后的交通方案可以继续切换',trip.days[0].ordered_stops[0].transit_from_previous.mode==='walk');
    await page.locator('#compute-all-routes').click();await settled(page);

    await page.locator('#generate-offline').click();await settled(page);
    check('离线预览显示景点及问路文本',await page.locator('#offline-preview').innerText().then(t=>t.includes('外滩')&&t.includes('Excuse me')));
    const download=page.waitForEvent('download');await page.locator('#download-offline').click();
    check('离线下载可用',(await download).suggestedFilename()==='visual_demo-offline.html');
    await page.locator('#load-offline').click();await settled(page);
    check('离线缓存恢复',await page.locator('#offline-status').innerText().then(t=>t.includes('载入')));
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('.day').evaluateAll(es=>es.forEach(e=>e.open=true));
    const changedHotel=anchors.hotels.find(h=>h.name_zh!==trip.anchor_hotel.name_zh);
    const originalHotel=anchors.hotels.find(h=>h.name_zh===trip.anchor_hotel.name_zh);
    const firstEnd=()=>page.locator('.day').first().locator('.day-point-select[data-field="end_anchor"]');
    check('每日卡包含起始点与终止点',await page.locator('.day-point-select').count()===4);
    await firstEnd().selectOption('hotel:'+changedHotel.id);await settled(page);
    check('当天终止点保存新酒店',trip.days[0].end_anchor?.name_zh===changedHotel.name_zh);
    check('翌日起点默认继承新酒店',await page.locator('.day').nth(1).locator('.day-sequence').innerText().then(t=>t.startsWith(changedHotel.name_zh)));
    check('换酒店清除旧交通',trip.days[0].ordered_stops.every(s=>s.transit_from_previous===null)&&await page.locator('.day-routes .route-card').count()===0);
    await page.evaluate(()=>{state.trip=structuredClone(state.trip);renderTrip();renderFlow();});
    check('重载后保留新酒店选择',await firstEnd().inputValue()==='hotel:'+changedHotel.id);
    await page.locator('.day').first().locator('.day-point-search').nth(1).fill('找不到的酒店');
    check('无匹配搜索保留已保存选择',await firstEnd().inputValue()==='hotel:'+changedHotel.id);
    await page.locator('.day').first().locator('.day-point-search').nth(1).fill('');
    simulateEndpointFailure=true;await firstEnd().selectOption('hotel:'+originalHotel.id);await settled(page);
    check('地点保存失败恢复旧选择',trip.days[0].end_anchor.name_zh===changedHotel.name_zh&&await firstEnd().inputValue()==='hotel:'+changedHotel.id);
    simulateEndpointFailure=false;
    await firstEnd().selectOption('');await settled(page);
    check('选择自动恢复默认住宿',trip.days[0].end_anchor===null&&await page.locator('.day').nth(1).locator('.day-sequence').innerText().then(t=>t.startsWith(trip.anchor_hotel.name_zh)));
    await firstEnd().selectOption('hotel:'+changedHotel.id);await settled(page);
    await page.locator('#setup-disclosure').evaluate(e=>e.open=true);
    await page.locator('#save-trip').click();await settled(page);
    check('全局保存保留每日酒店',trip.days[0].end_anchor.name_zh===changedHotel.name_zh);
    await page.locator('#setup-disclosure').evaluate(e=>e.open=false);
    await page.locator('#compute-all-routes').click();await settled(page);
    check('末段使用当天新酒店',await page.locator('.day').first().locator('.route-card').last().innerText().then(t=>t.includes(changedHotel.name_zh)));
    check('空景点日可以直接计算离境交通',await page.locator('.day').nth(1).locator('.route-card').innerText().then(t=>t.includes(changedHotel.name_zh)&&t.includes(trip.anchor_departure.location_name)));
    await page.locator('#generate-offline').click();await settled(page);
    check('离线预览展示每天起终点',await page.locator('#offline-preview').innerText().then(t=>t.includes('起点：')&&t.includes(changedHotel.name_zh)));
    check('演示路线没有导航入口',await page.locator('.navigation-link').count()===0&&await page.locator('.navigation-unavailable').first().innerText().then(t=>t.includes('演示')));
    // 下列是隔离 Amap 响应夹具，外部请求仍全部阻止，不调用真实高德。
    simulateRealRoutes=true;
    await page.locator('#compute-all-routes').click();await settled(page);
    const firstRoute=()=>page.locator('.day').first().locator('.route-card').first();
    const nativeLink=()=>firstRoute().locator('.navigation-link').first();
    check('真实方案夹具提供公交导航链接',new URL(await nativeLink().getAttribute('href')).searchParams.get('mode')==='bus');
    check('导航链接使用安全的新窗口',await nativeLink().getAttribute('target')==='_blank'&&(await nativeLink().getAttribute('rel')).includes('noopener'));
    check('返程导航使用当日新酒店',new URL(await page.locator('.day').first().locator('.route-card').last().locator('.navigation-link').first().getAttribute('href')).searchParams.get('to').endsWith(changedHotel.name_zh));
    const directURL=new URL(await page.locator('.day').nth(1).locator('.navigation-link').first().getAttribute('href'));
    check('空日导航从新酒店到离境口岸',directURL.searchParams.get('from').endsWith(changedHotel.name_zh)&&directURL.searchParams.get('to').endsWith(trip.anchor_departure.location_name));
    await firstRoute().locator('.route-details>summary').click();
    check('路线详情展示乘车站及步行说明',await firstRoute().locator('.route-detail-content').innerText().then(t=>t.includes('测试起点站上车')&&t.includes('测试终点站下车')&&t.includes('步行到测试车站')));
    check('完整轨迹展示线路形状',await firstRoute().locator('svg.route-shape polyline').count()===1);
    await firstRoute().getByRole('button',{name:/步行 ·/}).click();await settled(page);
    check('切换步行同步导航模式',new URL(await nativeLink().getAttribute('href')).searchParams.get('mode')==='walk');
    await page.evaluate(()=>{globalThis.__savedFlowRoutes=flow.routes;flow.routes={};renderTrip();renderFlow();});
    check('重载采用方案后保留步行导航',new URL(await nativeLink().getAttribute('href')).searchParams.get('mode')==='walk');
    await page.evaluate(()=>{flow.routes=globalThis.__savedFlowRoutes;renderTrip();renderFlow();});
    await firstRoute().getByRole('button',{name:/打车 ·/}).click();await settled(page);
    check('打车导航指向有效落客点',new URL(await nativeLink().getAttribute('href')).searchParams.get('mode')==='car'&&new URL(await nativeLink().getAttribute('href')).searchParams.get('to').endsWith('隔离测试落客点'));
    const beforeExternal=externalRequests.length;
    await page.evaluate(()=>{state.busy=true;document.querySelector('.navigation-link').click();state.busy=false;});
    check('保存期间阻止打开旧导航',externalRequests.length===beforeExternal&&await page.locator('#toast').innerText().then(t=>t.includes('正在修改')));
    const popupPromise=context.waitForEvent('page');await nativeLink().click();const popup=await popupPromise;
    await page.waitForFunction(()=>true);
    await new Promise(resolve=>setTimeout(resolve,150));
    check('明确点击才请求高德且外部请求已阻止',externalRequests.slice(beforeExternal).some(u=>new URL(u).hostname==='uri.amap.com'&&new URL(u).searchParams.get('callnative')==='1'));
    await popup.close();
    await firstRoute().getByRole('button',{name:/步行 ·/}).click();await settled(page);
    await page.evaluate(()=>{const poi=state.pois.find(p=>p.poi_id===state.trip.days[0].ordered_stops[0].poi_id);globalThis.__savedPoiCoordinate=poi.coordinate;poi.coordinate=null;renderTrip();renderFlow();});
    check('无效坐标不展示导航入口',await firstRoute().locator('.navigation-link').count()===0);
    await page.evaluate(()=>{state.pois.find(p=>p.poi_id===state.trip.days[0].ordered_stops[0].poi_id).coordinate=globalThis.__savedPoiCoordinate;renderTrip();renderFlow();});
    await firstRoute().getByRole('button',{name:/公共交通 ·/}).click();await settled(page);
    await firstRoute().locator('.route-details>summary').click();
    await firstRoute().screenshot({path:path.join(output,'route-navigation-desktop.png')});
    // 提醒展示夹具，不改变景点安排或真实规则数据。
    await page.evaluate(()=>{
      const day=state.trip.days[0],stop=day.ordered_stops[0],poi=state.pois.find(p=>p.poi_id===stop.poi_id);
      const context={day_index:day.day_index,date:day.date,poi_id:poi.poi_id,poi_name_zh:poi.names['zh-Hans'],arrival_local:'14:10'};
      flow.evaluations={notices:[
        {severity:'soft_warning',message_key:'rule.lightup.too_early',message_args:{...context,T_light:'18:30',light_start:'19:00',light_close:'23:00'}},
        {severity:'hard',outcome:'pending',message_key:'rule.closure.confirm',message_args:{notice_id:`rule_01_closure:${day.day_index}:${poi.poi_id}`,poi_name:poi.names.en,weekday:'Monday'}}
      ],overflow:1,overflow_notices:[{severity:'soft_hint',message_key:'rule.closure.data_unverified',message_args:{...context,poi_name:poi.names.en}}],skipped_rules:[]};
      renderFlow();
    });
    const reminderPanel=page.locator('#rules-panel');
    check('提醒分成需要处理建议核实三组',await reminderPanel.locator('.reminder-group').count()===3);
    check('夜景提醒写明景点日期和真实比较时间',await reminderPanel.locator('.reminder-suggest').innerText().then(t=>t.includes('第1天')&&t.includes('14:10')&&t.includes('18:30')&&t.includes('19:00–23:00')&&!t.includes('夜景景点：')));
    check('原先隐藏的核实提醒完整展示',await reminderPanel.locator('.reminder-verify').innerText().then(t=>t.includes('开放与闭馆信息尚未核实')));
    check('闭馆提醒保留两种处理按钮',await reminderPanel.getByRole('button',{name:'仍然保留',exact:true}).count()===1&&await reminderPanel.getByRole('button',{name:'移除此景点',exact:true}).count()===1);
    await page.locator('.day').evaluateAll(es=>es.forEach(e=>e.open=false));
    await reminderPanel.locator('.reminder-suggest').getByRole('button',{name:'调整当天安排'}).click();
    check('提醒调整按钮打开对应日且聚焦',await page.locator('.day').first().evaluate(e=>e.open&&e.querySelector('.day-summary')===document.activeElement));
    await page.locator('#toast').evaluate(e=>e.hidden=true);
    const screenshotStyle=await page.addStyleTag({content:'.workspace-nav,.form-actions,.back-top{visibility:hidden!important}'});
    await page.setViewportSize({width:1440,height:1100});await reminderPanel.screenshot({path:path.join(output,'trip-reminders-desktop.png')});
    await page.setViewportSize({width:390,height:844});await reminderPanel.screenshot({path:path.join(output,'trip-reminders-mobile.png')});
    await screenshotStyle.evaluate(e=>e.remove());
    await page.evaluate(()=>{
      globalThis.__reminderRoute=state.trip.days[0].ordered_stops[0].transit_from_previous;
      state.trip.days[0].ordered_stops[0].transit_from_previous=null;
      flow.evaluations={notices:[],skipped_rules:[{rule_id:'rule_02_lightup',reason:'missing_route_duration'}]};renderFlow();
    });
    check('缺交通提示具体日期及计算入口',await reminderPanel.innerText().then(t=>t.includes('还不能完整判断')&&t.includes('第1天')&&t.includes('1段交通'))&&await reminderPanel.getByRole('button',{name:'计算第1天交通',exact:true}).count()===1);
    await reminderPanel.getByRole('button',{name:'计算第1天交通',exact:true}).click();await settled(page);
    check('提醒内计算交通接入原计算流程',trip.days[0].ordered_stops.every(s=>s.transit_from_previous?.duration_seconds!=null));
    await page.evaluate(()=>{state.trip.days[0].ordered_stops[0].transit_from_previous=globalThis.__reminderRoute;renderTrip();renderFlow();});
    for(const width of [1440,768,390,320]) await layout(page,width);
    await page.emulateMedia({reducedMotion:'reduce'});
    check('减少动态效果有效',await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior==='auto'&&getComputedStyle(document.getElementById('save-trip')).transitionDuration==='0s'));
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('#toast').evaluate(e=>e.hidden=true);await page.evaluate(()=>window.scrollTo(0,0));
    await page.locator('#setup-disclosure').evaluate(e=>e.open=false);
    await page.locator('.day').evaluateAll(es=>es.forEach(e=>e.open=false));
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:path.join(output,'day-cards-desktop-overview.png')});
    await page.locator('.day-summary').first().click();
    await page.locator('#trip-panel').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'day-cards-desktop-expanded.png')});
    await page.screenshot({path:path.join(output,'soft-utility-desktop-overview.png')});
    await page.screenshot({path:path.join(output,'soft-utility-desktop.png'),fullPage:true});
    await page.locator('.workspace-nav a[href="#trip-panel"]').click();
    check('导航定位可见行程与交通',await page.evaluate(()=>document.getElementById('trip-panel').getBoundingClientRect().top>=0&&document.getElementById('trip-panel').getBoundingClientRect().top<200));
    await page.screenshot({path:path.join(output,'soft-utility-routes.png')});
    await page.setViewportSize({width:390,height:844});await page.locator('.back-top').click();
    await page.locator('.day').evaluateAll(es=>es.forEach(e=>e.open=false));
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:path.join(output,'day-cards-mobile-overview.png')});
    await page.locator('.day-summary').first().click();
    await page.locator('.day-summary').first().scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'day-cards-mobile-expanded.png'),fullPage:true});
    await page.screenshot({path:path.join(output,'soft-utility-mobile.png'),fullPage:true});
    await page.locator('.workspace-nav a[href="#setup-panel"]').click();
    await page.locator('#duration-days').focus();
    check('键盘焦点可见',await page.locator('#duration-days').evaluate(e=>getComputedStyle(e).outlineStyle==='solid'));
    await page.locator('.workspace-nav a[href="#poi-panel"]').click();
    await page.locator('.poi .link-button').first().click();
    check('手机弹窗关闭按钮在视窗内',await page.locator('#detail-close').evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;}));
    await page.screenshot({path:path.join(output,'soft-utility-detail-mobile.png')});await page.locator('#detail-close').click();
    const mobileBar=await page.evaluate(()=>{const bar=document.querySelector('.form-actions').getBoundingClientRect();document.querySelector('.day').open=true;const daily=document.querySelector('.day-start-input');daily.scrollIntoView({block:'center'});return {height:bar.height,bottom:bar.bottom};});
    check('手机底栏处于视窗底部',mobileBar.bottom===844&&mobileBar.height<100);
    for(const [fg,bg] of [['203b40','ffffff'],['50696d','ffffff'],['ffffff','2d5b63'],['244d45','d6ece5'],['654118','f9e5c9'],['813e38','fff5f3'],['364f76','e3eaf7']]) {
      const l1=luminance(fg),l2=luminance(bg);check(`文字对比度 #${fg}/#${bg} ≥ 4.5`,(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05)>=4.5);
    }
    // 仅在隔离页面展示六日色板，不保存，不请求新的业务数据。
    await page.setViewportSize({width:1440,height:1100});
    await page.evaluate(()=>{
      state.trip=structuredClone(state.trip);
      state.trip.days=Array.from({length:6},(_,i)=>i===0 ? state.trip.days[0] : {
        ...structuredClone(state.trip.days[1]),day_index:i+1,date:`2026-10-${12+i}`,ordered_stops:[]
      });
      renderTrip();renderFlow();document.getElementById('setup-disclosure').open=false;
      document.querySelectorAll('.day').forEach(e=>e.open=false);
    });
    const palette=await page.locator('.day').evaluateAll(es=>es.map(e=>({
      bg:getComputedStyle(e.querySelector('summary')).backgroundColor,
      text:getComputedStyle(e.querySelector('.day-metrics')).color,
      accent:getComputedStyle(e.querySelector('.day-number')).backgroundColor,
      badge:getComputedStyle(e.querySelector('.day-number')).color
    })));
    check('六日色板均有不同底色',new Set(palette.map(p=>p.bg)).size===6);
    const rgbHex=rgb=>rgb.match(/\d+/g).slice(0,3).map(v=>Number(v).toString(16).padStart(2,'0')).join('');
    for(let i=0;i<palette.length;i++) for(const [label,fg,bg] of [
      ['摘要',palette[i].text,palette[i].bg],['日期',palette[i].badge,palette[i].accent]
    ]) {
      const f=luminance(rgbHex(fg)),b=luminance(rgbHex(bg));
      check(`Day ${i+1} ${label}文字对比度 ≥ 4.5`,(Math.max(f,b)+.05)/(Math.min(f,b)+.05)>=4.5);
    }
    await page.locator('#trip-panel').screenshot({path:path.join(output,'day-cards-color-palette.png')});
    await page.evaluate(()=>{state.trip.days.forEach(d=>d.ordered_stops=[]);renderTrip();renderFlow();});
    trip.days.forEach(d=>d.ordered_stops=[]);
    check('全程无景点时仍可计算起终点交通',await page.locator('#compute-all-routes').isEnabled());
    check('浏览器及 API 无运行错误',errors.length===0);
    fs.writeFileSync(path.join(output,'day-cards-verification.json'),JSON.stringify({checks,errors,apiCalls:calls.length,viewports:[1440,768,390,320],isolated:true},null,2));
    console.log(`${checks.length} browser checks passed; screenshots: ${output}`);
  } finally {if(browser) await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
