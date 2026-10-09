const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node {
 constructor(tag,cls='',text=''){Object.assign(this,{tagName:tag,className:cls,textContent:text,children:[],dataset:{},events:{},open:true});}
 append(...n){this.children.push(...n);} replaceChildren(...n){this.children=n;} setAttribute(){} addEventListener(e,f){this.events[e]=f;}
 focus(){this.focused=true;} scrollIntoView(){this.scrolled=true;}
}
const hotel={stop_id:'one',stop_type:'hotel',name_zh:'住宿A',name_en:'Hotel A',poi_id:null,coordinate:{lat:31,lng:121,crs:'WGS84'},stop_order:1,planned_dwell_minutes:480,arrival_at:100,departure_at:28900,rule_notices:[]};
const day={day_index:1,date:'2026-10-12',daily_start_local:'09:00',ordered_stops:[hotel,{...hotel,stop_id:'two',stop_order:2,hotel_stay_kind:'rest'}]};
const trip={trip_id:'t',days:[day],resolved_day_points:{1:{start:hotel,end:hotel}},default_day_points:{1:{start:hotel,end:hotel}}};
const ctx={state:{trip,pois:[]},flow:{routes:{},evaluations:{}},element:(...a)=>new Node(...a),hhmm:String,weekdayZh:()=>'',engineReady:()=>true,$:()=>null,dayStatusLabel:()=>'',removeStop:(d,id)=>{ctx.removed=id;},setCurrentDay:()=>{}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('modules/web_workbench/web/poi_content.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/day_cards.js','utf8'),ctx);
const box=new Node('div');ctx.renderDayCards(trip,box);
const all=n=>[n,...n.children.flatMap(all)];let nodes=all(box);
assert.equal(ctx.dayPoiName(hotel),'住宿A');
assert.equal(ctx.dayCardSummary(trip,day).count,0,'lodging does not count as sightseeing');
const remove=nodes.find(n=>n.textContent==='移除');remove.events.click();assert.equal(ctx.removed,'one');
const collapse=nodes.find(n=>n.tagName==='button' && n.textContent==='收起详情');assert.ok(collapse,'bottom collapse exists');
box.children[0].open=true;collapse.events.click();assert.equal(box.children[0].open,false);
assert.ok(nodes.filter(n=>n.textContent==='住宿A').length===2,'intentional repeated stops are kept');
assert.ok(nodes.some(n=>n.textContent==='过夜住宿 480 分钟'),'legacy hotel stops retain overnight purpose');
assert.ok(nodes.some(n=>n.textContent==='休息 480 分钟'),'rest is clearly distinguished from overnight');
console.log('Anchor cards: names, counts, stable removal, bottom collapse, repeats passed');
