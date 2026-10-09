const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const calls = [];
const trip = {trip_id:'trip_saved', version:7, days:[]};
const nodes = new Map();
const node = () => ({children:[],attrs:{},setAttribute(key,value){this.attrs[key]=value;}, append(...xs){this.children.push(...xs);}, replaceChildren(){this.children=[];}, addEventListener(){}});
const ctx = {console, state:{pois:[], trip:null}, localStorage:{getItem:()=> 'trip_saved', setItem(){}},
  $:id => {if(!nodes.has(id)) nodes.set(id,node()); return nodes.get(id);},
  element:(tag,className,text)=>({...node(),className,textContent:text}), renderTrip(){}, redrawMap(){}, renderPoiList(){}, notify(){}, loadDraft:()=>null, formFromTrip(){},
  api:async path => {calls.push(path); return path === '/api/trips' ? {trips:[{trip_id:'trip_saved',start_date:'2026-10-12',duration_days:2}],trip_ids:['trip_saved']} : trip;}
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/offline_view.js','utf8'),ctx);
const file = 'modules/web_workbench/web/flow.js';
assert.ok(fs.existsSync(file), 'flow.js should exist');
vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
(async () => {
  await ctx.restoreHistory();
  assert.equal(ctx.state.trip.trip_id,'trip_saved');
  assert.ok(calls.includes('/api/trips/trip_saved'));
  ctx.state.trip = {trip_id:'trip_saved', days:[{day_index:1,ordered_stops:[{poi_id:'a'}]}],
    user_profile:{party_composition:'solo'}};
  ctx.state.services = {services:[{module_id:'route_adapter',ready:false,
    detail:'未读取 AMAP_WEB_KEY，请重新启动软件'}]};
  const beforeUnavailable = calls.length;
  assert.equal(await ctx.computeDayRoutes(1), false);
  assert.equal(calls.length, beforeUnavailable, 'unconfigured service must not receive route requests');
  assert.ok(nodes.get('route-progress').textContent.includes('AMAP_WEB_KEY'));
  const partialRoute = {mode:'transit',duration_seconds:null,data_source:'amap',partial:true,
    degraded_reason:'no_route',from:{name_zh:'金茂大厦'},to:{name_zh:'上海环球金融中心'},variants:[
      {mode:'transit',duration_seconds:null},{mode:'walk',duration_seconds:338,distance_meters:423}]};
  const routeBox=node();ctx.renderRoute(routeBox,1,0,partialRoute);
  const routeNodes=routeBox.children[0].children;
  assert.ok(routeNodes.some(n=>n.textContent?.includes('公共交通暂不可用')));
  assert.ok(routeNodes.some(n=>n.textContent==='当前采用：未选择可用方案'));
  assert.ok(routeNodes.some(n=>n.textContent?.startsWith('步行')&&!n.disabled));
  assert.ok(routeNodes.some(n=>n.textContent?.startsWith('公共交通 ·')&&n.disabled));
  const routeTrip={trip_id:'trip_saved',version:7,days:[{day_index:1,ordered_stops:[{poi_id:'a'}]}]};
  ctx.state.trip=routeTrip;
  const originalApi=ctx.api;let routePatch;
  ctx.api=async(path,args)=>{routePatch=args.body;return routeTrip;};
  await ctx.saveRoute(1,1,partialRoute);
  assert.equal(routePatch.days[0].end_transit,partialRoute,'final route is persisted separately');
  assert.equal(routePatch.days[0].ordered_stops,undefined);
  await ctx.saveRoute(1,0,partialRoute);
  assert.equal(routePatch.days[0].ordered_stops[0].stop_order,1);
  await assert.rejects(()=>ctx.saveRoute(1,2,partialRoute));
  ctx.api=originalApi;
  ctx.state.trip = trip;
  const ordered = ctx.rankPois([
    {poi_id:'a',category:{level1:'nature'},names:{en:'A'},popularity_norm:1},
    {poi_id:'b',category:{level1:'history_culture'},names:{en:'B'},popularity_norm:0}
  ],['history_culture']);
  assert.equal(ordered[0].poi_id,'b');
  assert.equal(ctx.escapeOffline('<script>"&'), '&lt;script&gt;&quot;&amp;');
  const card = ctx.askCardText({template_key:'poi_arrival',args:{poi_name_zh:'外滩',poi_name_en:'The Bund'}});
  assert.ok(card.zh.includes('外滩'));
  assert.ok(card.en.includes('The Bund'));
  assert.equal(ctx.askCardText({template_key:'station_exit',args:{}}), null);
  // 消费真实 Python 打包器输出，避免前后端各自通过但字段接不上。
  const payload = JSON.parse(execFileSync('python', ['-X', 'utf8', '-c',
    'import json,sys; from modules.offline_kit.package import OfflinePackager; print(json.dumps(OfflinePackager().build(json.load(sys.stdin))))'
  ], {encoding:'utf8', input:JSON.stringify({days:[{day_index:1,date:'2026-10-12',ordered_stops:[{
    stop_order:1,stop_type:'poi',poi_id:'sh_poi_00042',arrival_at:null,
    transit_from_previous:{data_source:'mock',to:{name_zh:'外滩',name_en:'The Bund'},segments:[]}
  }]}]})}));
  const html = ctx.offlineContent({trip_version:1,generated_at:0,payload});
  assert.match(html, /<h3(?:\s[^>]*)?>外滩 \/ The Bund<\/h3>/);
  assert.ok(html.includes('演示路线，不能用于真实导航。'));
  console.log('flow: history restore, interest ranking, export escaping, bilingual cards passed');
})().catch(err => {console.error(err); process.exitCode=1;});
