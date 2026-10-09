"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const WEB = path.resolve(__dirname, '../modules/web_workbench/web');

// Text nodes behave like DOM textContent; any attempt to interpret data as HTML fails.
class Node {
  constructor(tag, className='', text='') {
    Object.assign(this, {tagName:tag, className, children:[], dataset:{}, events:{}, value:'', hidden:false});
    this.textContent = text;
  }
  get textContent() { return this.ownText + this.children.map(n=>n.textContent).join(''); }
  set textContent(value) { this.ownText = value == null ? '' : String(value); this.children = []; }
  set innerHTML(_) { throw Error('POI data must be rendered as text, never HTML'); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.ownText=''; this.children=nodes; }
  setAttribute() {}
  addEventListener(type, fn) { this.events[type]=fn; }
  showModal() { this.open=true; }
}
const nodesIn = node => [node,...node.children.flatMap(nodesIn)];
const byClass = (node, name) => nodesIn(node).filter(n=>n.className.split(' ').includes(name));
function poi(description, id='p') {
  return {poi_id:id, names:{'zh-Hans':'测试景点', en:'Test POI'}, category:{level1:'history_culture',level2:'museum',label_zh:'博物馆'},
    description_zh:description, operating_rules:{dwell_time:{kind:'point',minutes:60}}};
}
function harness(pois=[poi('  沿江散步，欣赏城市景观。  ')]) {
  const html=fs.readFileSync(path.join(WEB,'index.html'),'utf8');
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Node('div')]));
  const calls=[];
  const ctx={state:{pois,trip:null,services:{ready:{}}}, $:id=>nodes.get(id)||null,
    element:(...args)=>new Node(...args), redrawMap(){},updateMapHint(){},resetAddConfirmation(){},
    hhmm:String,weekdayZh:()=>'',engineReady:()=>false,dayStatusLabel:()=>'',setCurrentDay(){},
    renderRoute(){},removeStop:(day,id)=>calls.push([day,id]),
    addStopControls:item=>item.append(new Node('div','stop-controls','锁定 上移 下移 移动到'))};
  vm.createContext(ctx);
  for (const file of ['poi_content.js','poi_list.js','poi_details.js','day_cards.js','recommendations.js']) {
    const source=path.join(WEB,file);
    if (fs.existsSync(source)) vm.runInContext(fs.readFileSync(source,'utf8'),ctx,{filename:file});
  }
  return {ctx,nodes,calls};
}
const tests=[];
const test=(name,run)=>tests.push([name,run]);
test('shared introduction trims text and explicitly falls back for old or invalid POIs',()=>{
  const {ctx}=harness();assert.equal(typeof ctx.poiIntroduction,'function','shared introduction reader is missing');
  assert.equal(ctx.poiIntroduction(poi('  完整简介  ')),'完整简介');
  for (const value of [undefined,null,'','  ',42,{},[]]) assert.equal(ctx.poiIntroduction(poi(value)),'简介待补充');
  assert.equal(ctx.poiIntroduction(null),'简介待补充');
});
test('POI cards show full introduction and retain category and dwell information',()=>{
  const {ctx,nodes}=harness();ctx.renderPoiList();const list=nodes.get('poi-list');
  assert.equal(byClass(list,'poi-introduction')[0]?.textContent,'沿江散步，欣赏城市景观。');
  assert.match(list.textContent,/博物馆.*建议游览 60 分钟/);
  assert.ok(nodesIn(list).some(n=>n.textContent==='详情' && n.events.click));
});
test('detail drawer shows full introduction below its names',()=>{
  const {ctx,nodes}=harness();ctx.openDetail(ctx.state.pois[0]);
  assert.equal(nodes.get('d-introduction')?.textContent,'沿江散步，欣赏城市景观。');
  assert.equal(nodes.get('detail').open,true);
});
test('daily editor puts introduction below POI name, skips anchors and preserves stop identity and controls',()=>{
  const {ctx,calls}=harness();const stops=[
    {stop_id:'stable-stop',poi_id:'p',stop_order:1,planned_dwell_minutes:60,locked:true},
    {stop_id:'hotel-stop',poi_id:'p',stop_type:'hotel',name_zh:'酒店',stop_order:2,planned_dwell_minutes:480},
    {stop_id:'arrival-stop',poi_id:'p',stop_type:'arrival_anchor',name_zh:'抵达口岸',stop_order:3,planned_dwell_minutes:90},
    {stop_id:'departure-stop',poi_id:'p',stop_type:'departure_anchor',name_zh:'离境口岸',stop_order:4,planned_dwell_minutes:90}];
  const trip={trip_id:'t',days:[{day_index:1,date:'2026-10-12',daily_start_local:'09:00',ordered_stops:stops}]};
  ctx.state.trip=trip;const box=new Node('div');ctx.renderDayCards(trip,box);
  const rows=byClass(box,'stop');assert.equal(byClass(rows[0],'poi-introduction')[0]?.textContent,'沿江散步，欣赏城市景观。');
  const name=byClass(rows[0],'stop-name')[0];const intro=byClass(rows[0],'poi-introduction')[0];
  assert.ok(nodesIn(rows[0]).indexOf(name)<nodesIn(rows[0]).indexOf(intro));
  for (const row of rows.slice(1)) assert.equal(byClass(row,'poi-introduction').length,0);
  assert.equal(byClass(rows[0],'stop-locked')[0]?.textContent,'已固定');
  assert.match(byClass(rows[0],'stop-controls')[0]?.textContent,/锁定.*上移.*下移.*移动到/);
  nodesIn(rows[0]).find(n=>n.textContent==='移除').events.click();assert.deepEqual(calls,[[1,'stable-stop']]);
});
function showRecommendations(ctx, stops) {
  ctx.testResult={plan:{days:[{day_index:2,stops}]},days:[{day_index:2,date:'2026-10-13',stops}],warnings:[],skipped_days:[]};
  vm.runInContext('recommendationView.result = testResult;',ctx);ctx.renderRecommendationResults();
}
test('recommendations show each POI introduction separately from its own reason',()=>{
  const {ctx,nodes}=harness([poi('甲景点简介','p'),poi('乙景点简介','q')]);
  showRecommendations(ctx,[{poi_id:'p',name_zh:'甲景点',planned_dwell_minutes:60,reasons:['甲推荐理由'],warnings:['甲核验提示']},
    {poi_id:'q',name_zh:'乙景点',planned_dwell_minutes:90,reasons:['乙推荐理由']}]);
  const box=nodes.get('recommendation-results');const stops=byClass(box,'recommendation-stop');assert.equal(stops.length,2);
  assert.equal(byClass(stops[0],'poi-introduction')[0]?.textContent,'甲景点简介');
  assert.equal(byClass(stops[1],'poi-introduction')[0]?.textContent,'乙景点简介');
  assert.match(byClass(stops[0],'recommendation-reason')[0]?.textContent,/甲推荐理由/);
  assert.doesNotMatch(byClass(stops[0],'recommendation-reason')[0]?.textContent,/甲景点简介|乙推荐理由/);
  assert.match(stops[0].textContent,/甲核验提示/);
});
test('all four surfaces show fallback for missing fields and display HTML-shaped text literally',()=>{
  const payload='<img src=x onerror="alert(1)">文本';
  for (const description of [undefined,payload]) {
    const expected=description || '简介待补充';const {ctx,nodes}=harness([poi(description)]);
    ctx.renderPoiList();assert.ok(nodes.get('poi-list').textContent.includes(expected));
    ctx.openDetail(ctx.state.pois[0]);assert.equal(nodes.get('d-introduction')?.textContent,expected);
    const trip={trip_id:'safe',days:[{day_index:2,date:'2026-10-13',daily_start_local:'09:00',ordered_stops:[{poi_id:'p',stop_order:1,planned_dwell_minutes:60}]}]};
    ctx.state.trip=trip;const box=new Node('div');ctx.renderDayCards(trip,box);assert.ok(box.textContent.includes(expected));
    showRecommendations(ctx,[{poi_id:'p',name_zh:'景点',planned_dwell_minutes:60,reasons:['理由']}]);
    assert.ok(nodes.get('recommendation-results').textContent.includes(expected));
    for (const root of [nodes.get('poi-list'),box,nodes.get('recommendation-results')]) assert.ok(!nodesIn(root).some(n=>n.tagName==='img'));
  }
});
test('unknown POI IDs have an explicit fallback in daily editor and recommendations',()=>{
  const {ctx,nodes}=harness([]);
  const stop={poi_id:'outside',stop_order:1,planned_dwell_minutes:60};
  const trip={trip_id:'old',days:[{day_index:2,date:'2026-10-13',daily_start_local:'09:00',ordered_stops:[stop]}]};
  ctx.state.trip=trip;const box=new Node('div');ctx.renderDayCards(trip,box);assert.match(box.textContent,/简介待补充/);
  showRecommendations(ctx,[{...stop,name_zh:'外部景点'}]);assert.match(nodes.get('recommendation-results').textContent,/简介待补充/);
});
let failed=0;
for (const [name,run] of tests) {try {run();console.log('ok',name);}catch(error){failed++;console.error('FAIL',name,error.message);}}
if (failed) process.exitCode=1;else console.log(`${tests.length}/${tests.length} POI introduction checks passed`);
