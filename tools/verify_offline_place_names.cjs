/* 验证指定行程的地名覆盖及四语真实导出；只读行程，--export 写独立 HTML。 */
"use strict";
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
const tripArg=args[args.indexOf('--trip')+1];
if(!args.includes('--trip') || !tripArg) throw new Error('Usage: node tools/verify_offline_place_names.cjs --trip <trip.json> [--export]');
const source=path.resolve(root,tripArg),original=fs.readFileSync(source),trip=JSON.parse(original);
const snapshot=JSON.parse(execFileSync('python',['-X','utf8','-c',
  'import json,sys; from modules.offline_kit.package import OfflinePackager; print(json.dumps(OfflinePackager().build(json.load(sys.stdin)),ensure_ascii=False))'],
  {cwd:root,encoding:'utf8',input:original,maxBuffer:10*1024*1024}));
const pkg={trip_id:trip.trip_id,trip_version:trip.version,package_version:'0.2.0',generated_at:Math.floor(Date.now()/1000),ttl_hours:24,payload:snapshot};
const stops=snapshot.days.flatMap(day=>[...day.stops,day.end_transfer].filter(Boolean));
const stations=stops.flatMap(stop=>stop.stations),walks=stops.flatMap(stop=>stop.walk_segments);
const chinese=/[\u3400-\u4dbf\u4e00-\u9fff]/;
for(const station of stations) {
  assert.ok(station.name_zh && station.name_en,`Missing station translation: ${station.name_zh}`);
  assert.ok(!chinese.test(station.name_en),station.name_en);
  for(const line of station.lines) {
    assert.ok(line.name_en && !chinese.test(line.name_en),`Missing line translation: ${line.name_zh}`);
    if(line.name_zh && line.name_zh.includes('--')) {
      assert.ok(line.name_en.includes(' — '),`Missing terminal pair: ${line.name_zh}`);
    }
    if(line.direction_zh) assert.ok(line.direction_en && !chinese.test(line.direction_en),line.direction_en);
  }
}
for(const walk of walks) if(walk.note_zh) assert.ok(walk.note_en && !chinese.test(walk.note_en),`Untranslated note: ${walk.note_zh}`);
const ctx={};ctx.window=ctx;vm.createContext(ctx);
for(const file of ['i18n_catalog.js','poi_i18n_catalog.js','common_i18n_catalog.js','offline_view.js'])
  vm.runInContext(fs.readFileSync(path.join(root,'modules/web_workbench/web',file),'utf8'),ctx);
let visibleCards=0;
for(const stop of stops) for(const card of stop.ask_cards) {
  const named=Object.entries(card.args).some(([key,value])=>key.endsWith('_zh') && value);
  if(!named) continue; // 三方没有出入口资料时保持隐藏，不能编造。
  for(const locale of ['zh-CN','en','ja','ko']) assert.ok(ctx.askCardText(card,locale),`Hidden named card: ${card.template_key}`);
  visibleCards++;
}
const files=[];
for(const locale of ['zh-CN','en','ja','ko']) {
  const html=ctx.offlineDocument(pkg,locale);
  assert.ok(html.includes(`lang="${locale}"`));
  assert.ok(!/<(?:script|link|img)\b/i.test(html),'Export must work with no external resources');
  for(const station of stations) {
    const display=ctx.offlineField(station,'name',locale);
    assert.ok(html.includes(ctx.escapeOffline(display)),display);
    if(locale==='ja' || locale==='ko') assert.ok(!/\b(?:Road|Line|Bus|Towards|Terminal)\b/.test(display),`English station label in ${locale}: ${display}`);
  }
  if(locale==='ja' || locale==='ko') {
    for(const walk of walks) if(walk.note_en) {
      const note=ctx.offlineWalkNote(walk,locale);
      assert.ok(note && note!==walk.note_zh,`Untranslated ${locale} walking note: ${walk.note_zh}`);
      assert.ok(!/\b(?:Walk|turn|continue|reach|arrive|along)\b/i.test(note),note);
      assert.ok(html.includes(ctx.escapeOffline(note)),note);
    }
  }
  for(const stop of stops) for(const card of stop.ask_cards) {
    const text=ctx.askCardText(card,locale);
    if(text) assert.ok(html.includes(ctx.escapeOffline(text.local)),text.local);
  }
  if(args.includes('--export')) {
    const output=path.join(root,'docs/验收截图',`offline-${trip.trip_id}-${locale}-2026-10-09.html`);
    fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,html);files.push(path.relative(root,output));
  }
}
assert.deepEqual(fs.readFileSync(source),original,'Packaging must not modify the saved trip');
console.log(JSON.stringify({trip_id:trip.trip_id,trip_version:trip.version,days:snapshot.days.length,
  station_entries:stations.length,unique_stations:new Set(stations.map(s=>s.name_zh)).size,
  line_entries:stations.reduce((n,s)=>n+s.lines.length,0),walking_notes:walks.filter(w=>w.note_zh).length,
  translated_terminal_pairs:stations.reduce((n,s)=>n+s.lines.filter(l=>l.name_en.includes(' — ')).length,0),
  visible_cards:visibleCards,locales:4,untranslated_stations:0,mixed_english_notes:0,trip_unchanged:true,files},null,2));
