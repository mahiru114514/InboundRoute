"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const ctx={window:null,document:{getElementById:()=>null}};ctx.window=ctx;vm.createContext(ctx);
const scripts=['i18n_catalog.js','poi_i18n_catalog.js','suggestions_i18n.js','common_i18n_catalog.js','common_i18n_patterns.js','onboarding_content.js','i18n.js'];
for(const file of scripts)vm.runInContext(fs.readFileSync(path.join(__dirname,'../modules/web_workbench/web',file),'utf8'),ctx,{filename:file});
const catalog=ctx.IRLanguageCatalog,keys=new Set(catalog.map(row=>row[0]));
assert.equal(keys.size,catalog.length,'All supplements and onboarding must coexist without duplicate keys');
assert.ok(catalog.every(row=>row.length===4&&row.every(value=>typeof value==='string'&&value.trim())));
const pois=['v1','v2'].flatMap(version=>JSON.parse(fs.readFileSync(path.join(__dirname,`../modules/trip_engine/data/shanghai_pois_${version}.json`),'utf8')));
function metadata(value,key='') {
  if(['names','romanization','search_aliases','description_zh'].includes(key))return;
  if(typeof value==='string'&&/[\u4e00-\u9fff]/.test(value))assert.ok(keys.has(value),`Missing exact metadata translation: ${value}`);
  else if(Array.isArray(value))value.forEach(item=>metadata(item));
  else if(value&&typeof value==='object')Object.entries(value).forEach(([key,item])=>metadata(item,key));
}
pois.forEach(poi=>metadata(poi));
const pricing=JSON.parse(fs.readFileSync(path.join(__dirname,'../modules/trip_engine/data/price_research_2026-10-06.json'),'utf8'));
function prices(value,key='') {
  if(key==='scope')assert.ok(keys.has(value),`Missing price scope: ${value}`);
  if(Array.isArray(value))value.forEach(item=>prices(item));
  else if(value&&typeof value==='object')Object.entries(value).forEach(([key,item])=>prices(item,key));
}
prices(pricing);
// Exercise actual backend output for every built-in attraction, both automatic
// and explicit accommodation, with real reference notes and missing-cost messages.
const python=String.raw`import json,tempfile
from pathlib import Path
from copy import deepcopy
from modules.trip_engine.engine import TripService
from tests.test_trip_engine import new_trip_payload
from core.budget_assessment import assess_trip
pois=sum([json.loads(Path('modules/trip_engine/data/shanghai_pois_'+v+'.json').read_text(encoding='utf-8')) for v in ('v1','v2')],[])
results=[]
with tempfile.TemporaryDirectory() as folder:
 service=TripService(Path(folder))
 base=service.create_trip(new_trip_payload(budget={'scope':'per_person','currency':'CNY','amount_cents':0}))
 for poi in pois:
  for manual in (False,True):
   trip=deepcopy(base)
   trip['days'][0]['ordered_stops']=[{'stop_id':'sample','stop_type':'poi','poi_id':poi['poi_id'],'planned_dwell_minutes':90,'coordinate':poi['coordinate']}]
   trip['cost_inputs']={'travelers':3,'lodging_rooms':2,'taxi_vehicles':1,'meal_daily_cents':5000,'intercity_cents':10000,'extras_cents':1000,'contingency_percent':10}
   if manual: trip['cost_inputs']['lodging_nights']=[{'date':'2026-10-12','hotel_name':'Custom Hotel','rooms':2,'room_price_cents':40000}]
   results.append(assess_trip(trip))
print(json.dumps(results,ensure_ascii=False))`;
const result=spawnSync(process.env.CONTENT_TEST_PYTHON||'python',['-c',python],{cwd:path.resolve(__dirname,'..'),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'},maxBuffer:8*1024*1024,windowsHide:true});
assert.equal(result.status,0,result.stderr);
const outputs=new Set();
function displayed(value,key='') {
  if(typeof value==='string'&&['label','message','title','body','reference_note','assumptions'].includes(key))outputs.add(value);
  else if(Array.isArray(value))value.forEach(item=>displayed(item,key));
  else if(value&&typeof value==='object')Object.entries(value).forEach(([key,item])=>displayed(item,key));
}
JSON.parse(result.stdout).forEach(item=>displayed(item));
const missing=[];
for(const original of outputs) {
  for(const code of ['en','ja','ko']) {
    const translated=ctx.IRLanguage.translate(original,code);
    assert.ok(translated.length,`${code}: ${original}`);
    if(code==='en'||code==='ko')if(/[\u4e00-\u9fff]/.test(translated.replaceAll('上海宏安瑞士大酒店','')))missing.push(`${code}: ${translated} (source: ${original})`);
  }
  assert.equal(ctx.IRLanguage.translate(original,'zh-CN'),original);
}
assert.deepEqual(missing,[],missing.join('\n'));
console.log(`Content coverage: ${catalog.length} unique complete rows, all 45 POI metadata sets, all price scopes and ${outputs.size} real budget messages in three languages passed`);
