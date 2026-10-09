const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
const hydrate=require('./trip_fixture');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('modules/web_workbench/web/day_points.js','utf8'),ctx);
const point=name=>({type:'hotel',name_zh:name,name_en:name,coordinate:{lat:31.2,lng:121.4,crs:'WGS84'}});
const trip={anchor_hotel:point('A'),anchor_arrival:{location_name:'机场',coordinate:point('A').coordinate},
  anchor_departure:{location_name:'车站',coordinate:point('A').coordinate},days:[1,2,3,4].map(day_index=>({day_index,ordered_stops:[]}))};
trip.days[1].end_anchor=point('B');
let resolved=ctx.resolveDayPoints(hydrate(trip));
assert.equal(resolved[1].start.name_zh,'机场');assert.equal(resolved[2].start.name_zh,'A');
assert.equal(resolved[3].start.name_zh,'B');assert.equal(resolved[3].end.name_zh,'B');
assert.equal(resolved[4].end.name_zh,'车站');
trip.days[2].start_anchor=point('C');resolved=ctx.resolveDayPoints(hydrate(trip));
assert.equal(resolved[3].end.name_zh,'C');assert.equal(resolved[4].start.name_zh,'C');
assert.equal(ctx.dayNeedsTransport(trip,trip.days[1]),true,'hotel change can compute with no POIs');
assert.equal(ctx.dayNeedsTransport(trip,trip.days[2]),false,'same hotel without POIs needs no route');
ctx.state={anchors:JSON.parse(fs.readFileSync('modules/trip_engine/data/anchors.json','utf8')),pois:[]};
const choices=ctx.dayPointOptions(trip,'end_anchor');
assert.ok(choices.some(c=>c.key==='hotel:hotel_peace' && c.anchor.coordinate.crs==='WGS84'),'real flat-coordinate hotel seed is selectable');
assert.ok(choices.some(c=>c.key==='hub:hub_hongqiao_t2' && c.anchor.type==='departure_anchor'),'real hub seed is selectable');
console.log('Day points: defaults, hotel inheritance, explicit override and direct transport passed');
class Node {constructor(tag,cls='',text=''){Object.assign(this,{tagName:tag,className:cls,textContent:text,children:[],dataset:{},value:'',events:{},open:false});}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(){}addEventListener(e,f){this.events[e]=f;}}
ctx.element=(...a)=>new Node(...a);const root=new Node('div');ctx.renderDayPoints(hydrate(trip),trip.days[0],root);
assert.equal(root.children[0].tagName,'details');assert.equal(root.children[0].open,false);assert.equal(root.children[0].children[0].textContent,'调整起终点');
