"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={};ctx.window=ctx;vm.createContext(ctx);
for(const file of ['i18n_catalog.js','poi_i18n_catalog.js','common_i18n_catalog.js','offline_view.js'])
  vm.runInContext(fs.readFileSync('modules/web_workbench/web/'+file,'utf8'),ctx);
const card={template_key:'poi_arrival',args:{poi_name_zh:'外滩',poi_name_en:'The Bund'}};
const stop={name_zh:'外滩',name_en:'The Bund',stop_type:'poi',ask_cards:[card,
  {template_key:'station_exit',args:{access_name_zh:'7号出口',access_name_en:'Exit 7'}}],
  stations:[{name_zh:'人民广场',name_en:"People's Square",lines:[{code:'2',name_zh:'2号线',name_en:'Line 2',direction_zh:'往浦东国际机场方向',direction_en:"Towards Pudong Int'l Airport"}],
    access_points:[{access_no:'7',kind:'exit',name_zh:'7号出口',name_en:'Exit 7'}]}],
  walk_segments:[{note_zh:'沿南京西路向东步行100米左转; 步行20米到达目的地',note_en:'Walk 100 m east along West Nanjing Road, turn left; Walk 20 m to arrive at your destination'}]};
const pkg={trip_version:1,generated_at:0,payload:{days:[{day_index:1,stops:[stop],end_transfer_required:false}]}};
const original=JSON.stringify(pkg);
for(const [locale,expected] of Object.entries({ja:['外灘（バンド）','人民広場','2号線','7番出口','浦東国際空港方面','左折','目的地に到着','1日目'],
  ko:['와이탄','인민광장','2호선','7번 출구','푸둥 국제공항 방면','좌회전','목적지에 도착','1일차']})) {
  const html=ctx.offlineContent(pkg,locale);
  for(const text of expected) assert.ok(html.includes(text),`${locale} should include ${text}`);
  for(const text of ['The Bund',"People&#39;s Square",'Line 2','Exit 7','Towards','Walk 100','turn left','Day 1'])
    assert.ok(!html.includes(text),`${locale} must not reuse English: ${text}`);
  const exported=ctx.offlineDocument(pkg,locale);
  assert.ok(exported.includes(html),'Preview and downloaded document use the same locale');
  assert.ok(!/<(?:script|link|img)\b/i.test(exported),'Downloaded HTML needs no network or scripts');
  ctx.IRLanguage={language:locale};assert.equal(ctx.offlineContent(pkg),html,'Live language selection applies');
}
assert.equal(JSON.stringify(pkg),original,'Switching languages does not alter the snapshot');
assert.ok(ctx.offlineContent(pkg,'en').includes('The Bund'),'English remains supported');
assert.ok(ctx.askCardText(card,'ja-JP').local.includes('外灘'),'Regional locale must not fall back to English');
assert.ok(ctx.askCardText(card,'ko-KR').local.includes('와이탄'));
const renamed={name_zh:'测试旅馆',name_en:'Ce Shi Inn',name_ja:'古いホテル',name_ja_for_zh:'旧旅馆'};
assert.ok(!ctx.offlineNames(renamed,'','ja').includes('古いホテル'),'Do not reuse a stale native name after renaming');
assert.ok(ctx.offlineNames({name_zh:'测试旅馆',name_en:'Ce Shi Inn'},'','ko').includes('여관'),'Unknown romanized names still localize place types');
const explicit={template_key:'poi_arrival',args:{poi_name_zh:'自选地点',poi_name_en:'Custom Place',poi_name_ja:'カスタム地点',poi_name_ko:'사용자 장소'}};
assert.ok(ctx.askCardText(explicit,'ja').local.includes('カスタム地点'));
assert.ok(ctx.askCardText(explicit,'ko').local.includes('사용자 장소'));
for(const locale of ['ja','ko']) {
  const complex=ctx.offlineWalkNote({note_zh:'向左前方直行下过街天桥',note_en:'Walk 212 m, bear left and continue and go down the pedestrian overpass'},locale);
  assert.ok(complex.includes(locale==='ja'?'歩道橋を下りる':'육교에서 내려가기'),'Compound instructions translate all actions');
}
const escaped={...stop,name_zh:'自选地点<script>',name_en:'Custom <script> Hotel'};
assert.ok(!ctx.offlineStopHTML(escaped,'ko').includes('<script>'),'Localized names are escaped');
console.log('Offline locales: native names, lines, direction, access, walks, cards, preview/export, switching, renaming and escaping passed');

// Exercise the actual language event, cached preview and download wiring.
const nodes=new Map(),listeners=new Map();let downloaded;
ctx.$=id=>{if(!nodes.has(id)) nodes.set(id,{addEventListener(){}});return nodes.get(id);};
ctx.document={getElementById:ctx.$,documentElement:{},body:{append(){}},createElement:()=>({click(){},remove(){}})};
ctx.addEventListener=(type,listener)=>listeners.set(type,listener);
ctx.dispatchEvent=event=>listeners.get(event.type)?.();ctx.Event=Event;
ctx.state={trip:{version:1}};ctx.Blob=Blob;
ctx.URL={createObjectURL(blob){downloaded=blob;return 'blob:test';},revokeObjectURL(){}};ctx.setTimeout=()=>{};
vm.runInContext(fs.readFileSync('modules/web_workbench/web/i18n.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/flow.js','utf8'),ctx);
ctx.testPackage=pkg;vm.runInContext('flow.offline=testPackage',ctx);
(async()=>{
  await ctx.initFlow();
  for(const locale of ['en','ja','ko','en']) {
    ctx.IRLanguage.setLanguage(locale,false);
    assert.equal(nodes.get('offline-preview').innerHTML,ctx.offlineContent(pkg,locale),'Language event refreshes an existing cached preview');
    ctx.downloadOffline();
    const html=await downloaded.text();
    assert.ok(html.includes(`lang="${locale}"`));
    assert.ok(html.includes(nodes.get('offline-preview').innerHTML),'Download uses the selected language after switching');
  }
  console.log('Offline locales: real language-change event and download wiring passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
