"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const file='modules/web_workbench/web/offline_view.js';
assert.ok(fs.existsSync(file),'Offline export renderer must exist');
const ctx={console};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
const templates=vm.runInContext('ASK_TEMPLATES',ctx);
const contract=JSON.parse(fs.readFileSync('contracts/mappings.json','utf8')).ask_card_templates;
for (const [key,translations] of Object.entries(templates)) {
  for (const lang of ['zh','en','ja','ko']) assert.equal(translations[lang],contract[key][lang],`${key}/${lang}`);
}
const card={template_key:'poi_arrival',args:{poi_name_zh:'外滩',poi_name_en:'The Bund'}};
assert.ok(ctx.askCardText(card,'ja').local.includes('どう'));
assert.ok(ctx.askCardText(card,'ko').local.includes('어떻게'));
assert.ok(ctx.askCardText(card,'ja').zh.includes('外滩'));
assert.equal(ctx.askCardText({template_key:'poi_arrival',args:{poi_name_zh:'外滩'}}),null);
const stop={name_zh:'外滩<script>',name_en:'The Bund',stop_type:'poi',arrival_at:0,departure_at:3600,
  mode:'transit',duration_seconds:1200,ask_cards:[card],
  stations:[{name_zh:'人民广场',name_en:"People's Square",lines:[{code:'2',name_zh:'2号线',name_en:'Line 2',color_hex:'#00a650'}],access_points:[{access_no:'7',kind:'exit',name_zh:'7号出口',name_en:'Exit 7'}]}],
  walk_segments:[{distance_meters:400,note_zh:'沿路直行',note_en:'Go straight'}]};
const pkg={trip_id:'t',trip_version:2,generated_at:0,ttl_hours:24,payload:{days:[{day_index:1,date:'2026-10-08',stops:[stop],end_transfer:{name_zh:'酒店',name_en:'Hotel',mode:'walk',duration_seconds:300,ask_cards:[],stations:[],walk_segments:[],data_source:'mock'}}]}};
const html=ctx.offlineContent(pkg,'en');
for(const value of ['Departure','09:00','Arrival','08:00','People&#39;s Square','Exit 7','Go straight','400','Final transfer','Demo route']) assert.ok(html.includes(value),value);
assert.ok(html.includes('外滩&lt;script&gt;'));assert.ok(!html.includes('<script>'));
assert.ok(!html.includes('variants') && !html.includes('congestion'));
const doc=ctx.offlineDocument(pkg,'ja');assert.ok(doc.includes('lang="ja"'));assert.ok(doc.includes('道案内'));assert.ok(doc.includes('外滩'));
assert.ok(!/<(?:script|link|img)\b/i.test(doc),'Export must have no external resources or scripts');
const old=ctx.offlineContent({trip_version:1,generated_at:0,payload:{days:[{day_index:1,stops:[{}]}]}},'en');
assert.ok(old.includes('unavailable') && old.includes('Final transfer'));
assert.ok(ctx.offlineContent({...pkg,generated_at:0},'en',86401).includes('outdated'));
const overnight=ctx.offlineContent({generated_at:0,payload:{days:[{day_index:1,date:'1970-01-01',stops:[{...stop,departure_at:61200}],end_transfer_required:false}]}},'en',0);
assert.ok(overnight.includes('1970-01-02 01:00'),'departures after midnight must include their actual China date');
console.log('Offline view: language, bilingual cards, station/access/walk details, timestamps, final leg, old data, TTL and escaping passed');

// 线路行：只显示线路名；三方主键不能当线路号；方向另起一行；号码已在线路名里就不重复。
const legacyLine={code:'900000160000',name_zh:'市域机场线(浦东1号2号航站楼--虹桥2号航站楼)',name_en:null,color_hex:null};
const railLine={code:'2',name_zh:'2 号线',name_en:'Line 2',color_hex:'#00A650',direction_zh:'往浦东国际机场方向',direction_en:"Towards Pudong Int'l Airport"};
const busLine={code:'18',name_zh:'闵行18路',name_en:'Bus 18',color_hex:null};
const lineStop={name_zh:'换乘站',name_en:'Transfer',stop_type:'poi',arrival_at:0,departure_at:600,ask_cards:[],walk_segments:[],
  stations:[{name_zh:'浦东1号2号航站楼',name_en:null,lines:[legacyLine,railLine,busLine],access_points:[{access_no:'1',kind:'entrance',name_zh:'1号口',name_en:'Entrance 1'}]}]};
const lineHtml=ctx.offlineContent({trip_version:1,generated_at:0,ttl_hours:24,payload:{days:[{day_index:1,date:'2026-10-12',stops:[lineStop]}]}},'en');
assert.ok(!lineHtml.includes('900000160000'),'三方主键不能出现在线路行里');
assert.ok(!lineHtml.includes('Line 2 ·'),'号码已经在线路名里就不再重复显示');
assert.ok(lineHtml.includes('市域机场线(浦东1号2号航站楼--虹桥2号航站楼)'),'方向推不出来时保留完整线路名');
assert.ok(lineHtml.includes('2 号线 / Line 2') && lineHtml.includes('闵行18路 / Bus 18'),'线路名（中/英）要显示');
assert.ok(lineHtml.includes('往浦东国际机场方向 / Towards Pudong Int'),'行车方向要显示');
assert.ok(lineHtml.includes('class="offline-line-direction"'),'方向用独立一行呈现');
const zhLineHtml=ctx.offlineContent({trip_version:1,generated_at:0,ttl_hours:24,payload:{days:[{day_index:1,date:'2026-10-12',stops:[lineStop]}]}},'zh-CN');
assert.ok(zhLineHtml.includes('往浦东国际机场方向'),'中文预览同样带方向');
assert.ok(!zhLineHtml.includes('900000160000'),'中文预览也不能出现三方主键');
console.log('Offline view: line identity (no provider ids), line name, direction row passed');

const labels=vm.runInContext("OFFLINE_LABELS",ctx);
for(const [key,row] of Object.entries(labels)) {assert.equal(row.length,4,key);assert.ok(row.every(text=>typeof text==='string'&&text.length),key);}
for(const code of ['zh-CN','en','ja','ko']){const exported=ctx.offlineDocument(pkg,code);assert.ok(exported.includes(`lang="${code}"`));const local=ctx.askCardText(card,code);assert.ok(exported.includes(ctx.escapeOffline(local.local)));assert.ok(exported.includes(ctx.escapeOffline(local.zh)));}

const reviewed=ctx.offlineContent({...pkg,payload:{...pkg.payload,translation_report:{status:'needs_review',candidate_count:1,missing_count:0,items:[{name_zh:'测试旅馆',name_en:'Ce Shi Inn',status:'candidate'}]}}},'en');
assert.ok(reviewed.includes('Unconfirmed place names'),'Candidate names require a visible localized warning');
assert.ok(reviewed.includes('Ce Shi Inn'));
const missing=ctx.offlineContent({...pkg,payload:{days:[],translation_report:{status:'missing',candidate_count:0,missing_count:1,items:[{name_zh:'生僻地名<script>',status:'missing'}]}}},'en');
assert.ok(missing.includes('生僻地名&lt;script&gt;'),'Missing-name report must escape user names');
