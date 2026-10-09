"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const WEB = path.resolve(__dirname, '../modules/web_workbench/web');
class Node {
  constructor(tag) { Object.assign(this, {tagName:tag, value:'', checked:false, children:[], events:{}, dataset:{}, hidden:false, disabled:false, textContent:'', classList:{remove(){},toggle(){}}}); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(type, fn) { (this.events[type] ||= []).push(fn); }
  setAttribute() {}
  get textContent() { return (this.ownText || '') + this.children.map(n=>n.textContent).join(''); }
  set textContent(value) { this.ownText=value == null ? '' : String(value); this.children=[]; }
}
const clone = value => JSON.parse(JSON.stringify(value));
function harness() {
  const html = fs.readFileSync(path.join(WEB,'index.html'),'utf8');
  const nodes = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1],new Node('div')]));
  const get = id => nodes.get(id) || null;
  const defaults = {'duration-days':'5',party:'solo',pacing:'balanced','arrival-date':'2026-10-12','arrival-time':'09:00','arrival-hub':'hub','hotel':'hotel'};
  for (const [id,value] of Object.entries(defaults)) if (get(id)) get(id).value=value;
  const storage = new Map();
  const calls=[], notices=[], edits=[];
  const ctx = {console,Date,Math,JSON,Number,String,Object,Array,Set,Map,Promise,
    document:{createElement: tag=>new Node(tag),querySelectorAll:()=>[],getElementById:get},
    localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)||null,removeItem:k=>storage.delete(k)},
    setTimeout:()=>0,clearTimeout(){},
    notify:(...args)=>notices.push(args),rememberTrip:()=>edits.push('remember'),
    renderTrip:()=>ctx.renderRecommendations(),resetFlowResults:()=>edits.push('reset'),
    refreshHistory:async()=>edits.push('history'),afterTripEditSafely:async trigger=>edits.push(trigger),
    tripDisplayName:()=> '行程',
    ymd:seconds=>new Date((seconds+28800)*1000).toISOString().slice(0,10),hhmm:seconds=>new Date((seconds+28800)*1000).toISOString().slice(11,16),
    state:{trip:null,busy:false,pickedHotel:null,services:{ready:{trip_engine:true,recommendation_engine:true}},anchors:{hubs:[{id:'hub',name_zh:'机场',name_en:'Airport',lat:31,lng:121}],hotels:[{id:'hotel',name_zh:'酒店',name_en:'Hotel',lat:31.2,lng:121.4}]}},
    api:async (url,options)=> {calls.push({url,options:clone(options)});return ctx.respond(url,options);},
  };
  vm.createContext(ctx);
  for (const script of ['poi_content.js','anchors.js','setup.js','recommendations.js']) {
    const file=path.join(WEB,script);
    if (fs.existsSync(file)) vm.runInContext(fs.readFileSync(file,'utf8'),ctx,{filename:script});
  }
  // runtime's lexical $ / element are represented by the same DOM helpers here.
  ctx.$=get; ctx.element=(tag,className,text)=>{const n=new Node(tag);n.className=className;n.textContent=text||'';return n;};
  ctx.respond=async url=>url==='/api/recommendations:generate'? proposal(): trip('created');
  return {ctx,get,calls,notices,storage,edits};
}
function trip(id='saved',n=5) {return {trip_id:id,version:8,budget:null,user_profile:{party_composition:'solo',pacing:'balanced',interests:[]},anchor_arrival:{at:1791766800,coordinate:{lat:31,lng:121,crs:'WGS84'}},anchor_hotel:{name_zh:'酒店',name_en:'Hotel',coordinate:{lat:31.2,lng:121.4,crs:'WGS84'}},days:Array.from({length:n},(_,i)=>({day_index:i+1,date:`2026-10-${12+i}`,ordered_stops:[]}))};}
function proposal(overrides={}) {return {plan:{days:[{day_index:2,stops:[{poi_id:'p',planned_dwell_minutes:60}]}]},days:[{day_index:2,date:'2026-10-13',stops:[{poi_id:'p',name_zh:'景点',planned_dwell_minutes:60,reasons:['符合历史兴趣'],warnings:['开放资料待核验']}]}],skipped_days:[],warnings:['交通仅为规划估算'],trip_id:null,trip_version:null,...overrides};}
function checkModule(ctx) {assert.equal(typeof ctx.renderRecommendations,'function','推荐日期与操作模块必须存在');}
const tests=[];
function test(name,fn) {tests.push([name,fn]);}
test('默认只选择中间日，首尾可手动选；1～2天默认无选',()=>{
  const {ctx,get}=harness();checkModule(ctx);ctx.renderRecommendations();
  const boxes=get('recommendation-days').children.map(label=>label.children[0]);
  assert.deepEqual(boxes.filter(n=>n.checked).map(n=>n.value),['2','3','4']);
  assert.equal(boxes[0].disabled,false);assert.equal(boxes[4].disabled,false);
  for (const length of [1,2]) {get('duration-days').value=String(length);ctx.renderRecommendations();assert.equal(get('recommendation-days').children.filter(label=>label.children[0].checked).length,0);assert.match(get('recommendation-hint').textContent,/勾选/);}
});
test('服务刷新保留用户选择，切换行程清除旧理由及恢复默认日期',()=>{
  const {ctx,get}=harness();checkModule(ctx);ctx.renderRecommendations();
  const boxes=get('recommendation-days').children.map(label=>label.children[0]);boxes[0].checked=true;boxes[1].checked=false;
  for (const fn of boxes[0].events.change) fn();for (const fn of boxes[1].events.change) fn();
  ctx.renderRecommendations();assert.deepEqual(get('recommendation-days').children.filter(label=>label.children[0].checked).map(label=>label.children[0].value),['1','3','4']);
  ctx.state.trip=trip('other');ctx.renderRecommendations();assert.deepEqual(get('recommendation-days').children.filter(label=>label.children[0].checked).map(label=>label.children[0].value),['2','3','4']);assert.equal(get('recommendation-results').children.length,0);
});
test('新建先计算再一次原子保存，显示理由、刷新历史与现有流程',async()=>{
  const {ctx,get,calls,edits}=harness();checkModule(ctx);ctx.renderRecommendations();const setup=clone(ctx.readSetup());
  await ctx.generateRecommendedTrip();
  assert.deepEqual(calls.map(c=>c.url),['/api/recommendations:generate','/api/trips:recommended']);
  assert.deepEqual(calls[0].options.body,{setup,day_indices:[2,3,4]});assert.deepEqual(calls[1].options.body,{setup,plan:proposal().plan});
  assert.equal(ctx.state.trip.trip_id,'created');assert.ok(edits.includes('add_stop'));assert.ok(edits.includes('history'));
  assert.match(get('recommendation-results').children.map(n=>n.textContent).join(' '),/符合历史兴趣.*开放资料待核验.*交通仅为规划估算/);
});
test('已有行程计算只传 id，应用传计算快照版本，不逐点写入',async()=>{
  const {ctx,calls}=harness();checkModule(ctx);ctx.state.trip=trip();ctx.formFromTrip(ctx.state.trip);ctx.renderRecommendations();
  ctx.respond=async url=>url==='/api/recommendations:generate'?proposal({trip_id:'saved',trip_version:7}):trip();
  await ctx.generateRecommendedTrip();
  assert.deepEqual(calls[0].options.body,{trip_id:'saved',day_indices:[2,3,4]});assert.equal(calls[1].url,'/api/trips/saved/recommendations:apply');assert.equal(calls[1].options.version,7);assert.deepEqual(calls[1].options.body,{plan:proposal().plan});
});
test('已有设定或预算未保存时提示先保存，既不 PATCH 也不计算',async()=>{
  for (const field of ['pacing','budget-per-person','hotel']) {
    const {ctx,get,calls,notices}=harness();checkModule(ctx);ctx.state.trip=trip();ctx.formFromTrip(ctx.state.trip);ctx.renderRecommendations();get(field).value=field==='pacing'?'packed':field==='hotel'?'missing':'10';
    await ctx.generateRecommendedTrip();assert.equal(calls.length,0);assert.match(notices.at(-1)[0],/先保存/);
  }
});
test('缺推荐模块或所有选中日期已有安排时禁用并解释',async()=>{
  const {ctx,get,calls,notices}=harness();checkModule(ctx);ctx.state.services.ready.recommendation_engine=false;ctx.renderRecommendations();assert.equal(get('generate-recommendations').disabled,true);await ctx.generateRecommendedTrip();assert.equal(calls.length,0);
  ctx.state.services.ready.recommendation_engine=true;ctx.state.trip=trip();ctx.state.trip.days.forEach(d=>d.ordered_stops=[{stop_type:'hotel',locked:true}]);ctx.formFromTrip(ctx.state.trip);ctx.renderRecommendations();await ctx.generateRecommendedTrip();assert.equal(calls.length,0);assert.match(notices.at(-1)[0],/已有安排|空白/);
});
test('无结果不落盘；计算失败和应用版本冲突均保留原行程及草稿',async()=>{
  for (const stage of ['empty','generate','apply']) {
    const {ctx,calls,storage}=harness();checkModule(ctx);ctx.state.trip=trip();ctx.formFromTrip(ctx.state.trip);ctx.renderRecommendations();ctx.saveDraft();const before=ctx.state.trip,draft=storage.get('inboundroute.setupDraft');
    ctx.respond=async url=>{if(stage==='empty')return proposal({plan:{days:[]},days:[],skipped_days:[{day_index:2,reason:'候选不足'}]});if(stage==='generate'||url.endsWith(':apply'))throw new Error('版本冲突 / 服务失败');return proposal({trip_id:'saved',trip_version:8});};
    await ctx.generateRecommendedTrip();assert.equal(ctx.state.trip,before);assert.equal(storage.get('inboundroute.setupDraft'),draft);assert.equal(calls.length,stage==='apply'?2:1);
  }
});
test('新建计算或保存失败保留自填住宿草稿且没有空壳行程',async()=>{
  for (const failAt of ['generate','save']) {
    const {ctx,get,calls,storage}=harness();checkModule(ctx);ctx.renderRecommendations();ctx.applyDraft({hotel_mode:'manual',hotel_name:'未保存民宿',picked_hotel:{lat:31.8,lng:121.8,crs:'WGS84'}});ctx.saveDraft();const draft=storage.get('inboundroute.setupDraft');
    ctx.respond=async url=>{if(failAt==='generate'||url==='/api/trips:recommended')throw new Error('服务不可用');return proposal();};
    await ctx.generateRecommendedTrip();assert.equal(ctx.state.trip,null);assert.equal(storage.get('inboundroute.setupDraft'),draft);assert.equal(ctx.readHotelAnchor().name_zh,'未保存民宿');assert.equal(calls.length,failAt==='generate'?1:2);assert.ok(!calls.some(c=>c.url==='/api/trips'));
  }
});
test('没有候选的理由与提示完整展示，不宣称已安排或保存',async()=>{
  const {ctx,get,calls}=harness();checkModule(ctx);ctx.renderRecommendations();ctx.respond=async()=>proposal({plan:{days:[]},days:[],skipped_days:[{day_index:2,reason:'没有合适的候选'}],warnings:['需核验资料']});
  await ctx.generateRecommendedTrip();const copy=get('recommendation-results').children.map(n=>n.textContent).join(' ');
  assert.match(copy,/没有合适的候选/);assert.match(copy,/需核验资料/);assert.doesNotMatch(copy,/推荐已按|推荐行程已保存/);assert.equal(calls.length,1);
});
test('未勾选日期或未选择住宿不会发出计算请求',async()=>{
  for (const scenario of ['dates','coordinate']) {
    const {ctx,get,calls,notices}=harness();checkModule(ctx);
    if(scenario==='dates')get('duration-days').value='2';else {get('hotel').value='';}
    ctx.renderRecommendations();await ctx.generateRecommendedTrip();assert.equal(calls.length,0);assert.match(notices.at(-1)[0],scenario==='dates'?/勾选/:/选择住宿/);
  }
});
test('双击只产生一次生成和写入，进度状态最终恢复',async()=>{
  const {ctx,get,calls}=harness();checkModule(ctx);ctx.renderRecommendations();let release;
  ctx.respond=url=>url==='/api/recommendations:generate'?new Promise(resolve=>release=()=>resolve(proposal())):Promise.resolve(trip());
  const first=ctx.generateRecommendedTrip();await ctx.generateRecommendedTrip();assert.equal(calls.length,1);assert.equal(ctx.state.busy,true);assert.match(get('recommendation-progress').textContent,/生成|计算/);release();await first;assert.equal(calls.length,2);assert.equal(ctx.state.busy,false);assert.equal(get('generate-recommendations').disabled,false);
});
test('推荐计算期间切换行程、修改原行程或更改新建设定会阻止保存',async()=>{
  for (const change of ['switch','version','settings','new-settings','new-budget']) {
    const {ctx,get,calls,storage,notices}=harness();checkModule(ctx);
    if(!change.startsWith('new-')) {ctx.state.trip=trip();ctx.formFromTrip(ctx.state.trip);}
    ctx.renderRecommendations();ctx.saveDraft();let release;
    ctx.respond=url=>url==='/api/recommendations:generate'
      ? new Promise(resolve=>release=()=>resolve(proposal({trip_id:ctx.state.trip?.trip_id || null,trip_version:8})))
      : Promise.resolve(trip('result'));
    const pending=ctx.generateRecommendedTrip();
    if(change==='switch') {ctx.state.trip=trip('other');ctx.formFromTrip(ctx.state.trip);}
    else if(change==='version')ctx.state.trip.version++;
    else get(change==='new-budget'?'budget-per-person':'pacing').value=change==='new-budget'?'100':'packed';
    ctx.saveDraft();const current=ctx.state.trip,draft=storage.get('inboundroute.setupDraft');
    release();await pending;assert.equal(calls.length,1,'上下文变化后不能发出 apply 或 create');assert.equal(ctx.state.trip,current);assert.equal(storage.get('inboundroute.setupDraft'),draft);assert.match(notices.at(-1)[0],/切换|更改|更新|重新/);
  }
});
test('保存请求期间切换行程不覆盖当前视图或丢弃新草稿',async()=>{
  const {ctx,calls,storage,notices}=harness();checkModule(ctx);ctx.state.trip=trip();ctx.formFromTrip(ctx.state.trip);ctx.renderRecommendations();let release;
  ctx.respond=url=>url==='/api/recommendations:generate'?Promise.resolve(proposal({trip_id:'saved',trip_version:8}))
    : new Promise(resolve=>release=()=>resolve(trip('saved')));
  const pending=ctx.generateRecommendedTrip();await new Promise(setImmediate);assert.equal(calls.length,2);
  ctx.state.trip=trip('other');ctx.formFromTrip(ctx.state.trip);ctx.saveDraft();const current=ctx.state.trip,draft=storage.get('inboundroute.setupDraft');release();await pending;
  assert.equal(ctx.state.trip,current);assert.equal(storage.get('inboundroute.setupDraft'),draft);assert.match(notices.at(-1)[0],/已保存.*当前|原行程/);
});
test('已保存自定义住宿可在统一搜索中找到并保留原名和精确坐标',()=>{
  const {ctx,get}=harness();const saved=trip();saved.anchor_hotel={name_zh:'我的民宿',name_en:'My Home',coordinate:{lat:31.8,lng:121.8,crs:'WGS84',precision_m:5},poi_id:null};
  ctx.formFromTrip(saved);get('hotel-search').value='My Home';ctx.renderAnchorPickers();const setup=ctx.readSetup();assert.deepEqual(clone(setup.anchor_hotel),saved.anchor_hotel);
  const snapshot=clone(ctx.formSnapshot());ctx.state.savedHotels=[];get('hotel').value='hotel';ctx.applyDraft(snapshot);assert.equal(ctx.readSetup().anchor_hotel.name_zh,'我的民宿');
  get('hotel-search').value='Hotel';ctx.renderAnchorPickers();assert.throws(()=>ctx.readSetup(),/选择住宿/);
});
(async()=>{let failed=0;for(const [name,fn]of tests){try{await fn();console.log('ok',name);}catch(error){failed++;console.error('FAIL',name,error.message);}}if(failed)process.exitCode=1;else console.log(`${tests.length}/${tests.length} recommendation checks passed`);})();
