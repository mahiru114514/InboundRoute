/* 隔离验收：仅使用契约样例与内存响应，不读取或修改用户行程。
 * node tools/verify_offline_preview.cjs [--serve]
 * 默认输出四语 HTML；--serve 同时在本机 59111 提供真实工作台静态文件和演示 API。
 */
"use strict";
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),http=require('node:http');
const {execFileSync}=require('node:child_process');
const {ASSETS,WEB}=require('./workbench_assets.cjs');
const root=path.resolve(__dirname,'..');
const route=JSON.parse(fs.readFileSync(path.join(root,'contracts/examples/route_transit_transfer.json'),'utf8'));
route.data_source='mock';
const anchors=JSON.parse(fs.readFileSync(path.join(root,'modules/trip_engine/data/anchors.json'),'utf8'));
const hotel={type:'hotel',name_zh:'验收示例住宿',name_en:'Demo Hotel',coordinate:{lat:31.23,lng:121.47,crs:'WGS84'}};
const arrival={type:'arrival_anchor',location_name:'验收示例起点 / Demo Start',name_zh:'验收示例起点',name_en:'Demo Start',at:1791817200,activity_start_at:1791817200,coordinate:{lat:31.24,lng:121.48,crs:'WGS84'}};
const trip={trip_id:'offline_demo',version:1,status:'draft',timezone:'Asia/Shanghai',
  user_profile:{party_composition:'solo',pacing:'balanced',interests:[],walking_speed_factor:1,party_walk_multiplier:1},
  anchor_arrival:arrival,anchor_hotel:hotel,days:[{day_index:1,date:'2026-10-12',day_status:'partial',daily_start_local:'09:00',poi_cap:4,
    ordered_stops:[{stop_id:'demo_stop',stop_order:1,stop_type:'poi',poi_id:'sh_poi_00088',planned_dwell_minutes:90,
      arrival_at:1791819600,departure_at:1791825000,transit_from_previous:route}],
    end_transit:{...route,from:route.to,to:hotel}}]};
const snapshot=JSON.parse(execFileSync('python',['-X','utf8','-c',
  'import json,sys; from modules.offline_kit.package import OfflinePackager; from core.trip_points import enrich_trip_points; trip=json.load(sys.stdin); print(json.dumps({"payload":OfflinePackager().build(trip),"trip":enrich_trip_points(trip)},ensure_ascii=False))'],
  {cwd:root,encoding:'utf8',input:JSON.stringify(trip)}));
Object.assign(trip,snapshot.trip);
const pkg={trip_id:trip.trip_id,trip_version:1,package_version:'0.2.0',generated_at:Math.floor(Date.now()/1000),ttl_hours:24,payload:snapshot.payload};
const ctx={};ctx.window=ctx;vm.createContext(ctx);
for(const file of ['i18n_catalog.js','poi_i18n_catalog.js','common_i18n_catalog.js','offline_view.js'])
  vm.runInContext(fs.readFileSync(path.join(WEB,file),'utf8'),ctx);
const output=path.join(root,'docs/验收截图');fs.mkdirSync(output,{recursive:true});
if (process.argv.includes('--json')) console.log(JSON.stringify(Object.fromEntries(['zh-CN','en','ja','ko'].map(locale=>[locale,ctx.offlineDocument(pkg,locale)]))));
for(const locale of process.argv.includes('--serve') || process.argv.includes('--json') ? [] : ['zh-CN','en','ja','ko']) {
  const name=`offline-package-${locale}-2026-10-08.html`;
  fs.writeFileSync(path.join(output,name),ctx.offlineDocument(pkg,locale));
  console.log(name);
}
if(process.argv.includes('--serve')) {
  const pois=JSON.parse(execFileSync('python',['-X','utf8','-c',
    'import json; from modules.trip_engine.poi_seed import POIS; print(json.dumps(POIS,ensure_ascii=False))'],{cwd:root,encoding:'utf8'}));
  const modules=['trip_engine','rules_engine','route_adapter','offline_kit'];
  http.createServer((req,res)=>{
    const url=new URL(req.url,'http://127.0.0.1'),pathname=url.pathname;
    const send=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify({ok:status===200,data}));};
    if(pathname==='/api/session') return send({token:'isolated-offline-test',map:{ready:false,provider:'none',hint:'离线包隔离验收'}});
    if(pathname==='/api/services') return send({services:modules.map(module_id=>({module_id,ready:true,health:'ok',purpose:'隔离验收',detail:'演示响应'})),ready:Object.fromEntries(modules.map(id=>[id,true]))});
    if(pathname==='/api/pois') return send({pois});
    if(pathname==='/api/anchors') return send(anchors);
    if(pathname==='/api/trips') return send({trips:[{trip_id:trip.trip_id,version:1,start_date:'2026-10-12',duration_days:1}]});
    if(pathname==='/api/trips/offline_demo') return send(trip);
    if(pathname.endsWith('/rules:evaluate')) return send({trip,notices:[],timeline:[],skipped_rules:[]});
    if(pathname.endsWith('/offline-package')) return send(pkg);
    const asset=ASSETS[pathname==='/' ? '/index.html' : pathname];
    if(asset) {res.writeHead(200,{'Content-Type':asset.mime});return res.end(fs.readFileSync(path.resolve(WEB,asset.file)));}
    const locale=/^\/preview\/(zh-CN|en|ja|ko)$/.exec(pathname)?.[1];
    if(locale) {res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});return res.end(ctx.offlineDocument(pkg,locale));}
    send(null,404);
  }).listen(59111,'127.0.0.1',()=>console.log('Isolated offline preview: http://127.0.0.1:59111'));
}
