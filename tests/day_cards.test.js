const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(tag, cls='', text='') {Object.assign(this,{tagName:tag,className:cls,textContent:text,children:[],dataset:{},open:false,events:{}});}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children=nodes;}
  setAttribute() {}
  addEventListener(name, fn) {this.events[name]=fn;}
}
const ctx={state:{pois:[{poi_id:'a',names:{'zh-Hans':'外滩'}}],services:{services:[]}},flow:{routes:{},evaluations:{}},
  element:(...args)=>new Node(...args),hhmm:t=>String(t),weekdayZh:()=>'',setCurrentDay:()=>{},dayStatusLabel:()=>'',
  addStopControls:()=>{},renderRoute:(box,d,i,r)=>box.append(new Node('article','route-card',r.mode)),
  engineReady:()=>false,flowAction:()=>{throw Error('Opening a card must not request services');},$:()=>null};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/poi_content.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/day_cards.js','utf8'),ctx);
const day={day_index:1,date:'2026-10-12',daily_start_local:'09:00',ordered_stops:[{poi_id:'a',stop_order:1,planned_dwell_minutes:90,arrival_at:null,departure_at:null,rule_notices:[]}]};
const trip={trip_id:'first',days:[day]};ctx.state.trip=trip;
let s=ctx.dayCardSummary(trip,day);
const arrivalTrip={...trip,anchor_arrival:{activity_start_at:12345}};
assert.equal(ctx.dayCardSummary(arrivalTrip,day).time,'12345 出发 · 结束待定','arrival day starts after the arrival buffer');
assert.equal(s.missing,1);assert.equal(s.complete,false);assert.equal(s.rulesLabel,'行程提醒暂不可用');
day.ordered_stops[0].transit_from_previous={mode:'walk',duration_seconds:0};
day.ordered_stops[0].arrival_at=0;day.ordered_stops[0].departure_at=5400;
s=ctx.dayCardSummary(trip,day);assert.equal(s.missing,0);assert.equal(s.complete,true);
const conflict={rule_id:'closed',severity:'hard',message_args:{notice_id:'closed:1:a'}};
day.ordered_stops[0].rule_notices=[conflict,conflict];
assert.equal(ctx.dayCardSummary(trip,day).conflicts,1);
const box=new Node('div');ctx.renderDayCards(trip,box);
const card=box.children[0];assert.equal(card.tagName,'details');assert.equal(card.open,false);
card.open=true;card.events.toggle();box.replaceChildren();ctx.renderDayCards(trip,box);assert.equal(box.children[0].open,true);
const next={...trip,trip_id:'second'};ctx.state.trip=next;box.replaceChildren();ctx.renderDayCards(next,box);assert.equal(box.children[0].open,false);
const same=box.children[0];ctx.syncDayCards();assert.equal(box.children[0],same,'service polling must preserve card nodes');
day.end_transit={mode:'taxi',duration_seconds:60};ctx.syncDayCards();
const allNodes=n=>[n,...n.children.flatMap(allNodes)];
assert.ok(allNodes(box).some(n=>n.className==='route-card' && n.textContent==='taxi'),'reload restores persisted final segment');
assert.ok(allNodes(box).some(n=>n.textContent==='返程已计算'));
assert.ok(!allNodes(box).some(n=>n.textContent.includes('终点区间请重新计算')));
delete day.end_transit;
box.children[0].open=true;box.children[0].events.toggle();ctx.updateSetupDisclosure(null);box.replaceChildren();ctx.renderDayCards(next,box);assert.equal(box.children[0].open,false,'new-trip selection resets disclosures');
day.ordered_stops=[];s=ctx.dayCardSummary(trip,day);assert.equal(s.complete,false);assert.equal(s.missing,0);
ctx.hhmm=()=> '11:00';ctx.ymd=()=> '2026-10-12';
const arrivalDay={...day,day_status:'arrival_only'};
const sameDateTrip={...trip,anchor_arrival:{activity_start_at:12345},days:[arrivalDay]};
ctx.state.trip=sameDateTrip;box.replaceChildren();ctx.renderDayCards(sameDateTrip,box);
let departure=box.children[0].children[1].children[0].children[0].children[0];
assert.equal(departure.disabled,false,'normal arrival day permits a later departure despite arrival_only status');
assert.equal(departure.value,'11:00');
ctx.hhmm=()=> '01:00';ctx.ymd=()=> '2026-10-13';
box.replaceChildren();ctx.renderDayCards(sameDateTrip,box);
departure=box.children[0].children[1].children[0].children[0].children[0];
assert.equal(departure.disabled,true,'arrival buffer beyond the day disables that day');
assert.equal(departure.value,'01:00','cross-midnight buffer displays its actual time');
assert.match(ctx.dayCardSummary(sameDateTrip,arrivalDay).time,/2026-10-13.*01:00/,'summary identifies the buffer date after midnight');
console.log('Day cards: pending routes, zero values, risk deduplication, disclosure state and polling passed');
