const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node{constructor(tag,c='',t=''){Object.assign(this,{tagName:tag,className:c,children:[],events:{},textContent:t,value:'',open:false});}append(...n){this.children.push(...n);for(const child of n)child.parentNode=this;}replaceChildren(...n){this.children=n;}setAttribute(){}addEventListener(e,f){this.events[e]=f;}}
const coordinate={lat:31,lng:121,crs:'WGS84'};
const hotel={type:'hotel',name_zh:'酒店',name_en:'Hotel',coordinate};
const trip={trip_id:'t',anchor_hotel:hotel,anchor_arrival:{location_name:'机场',coordinate},anchor_departure:{location_name:'口岸',coordinate},days:[{day_index:1,ordered_stops:[]}]};
const ctx={state:{trip,anchors:{},pois:[]},element:(...a)=>new Node(...a),flowAction:f=>f(),addAnchorStop:async(...args)=>ctx.calls.push(args),calls:[]};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('modules/web_workbench/web/day_points.js','utf8'),ctx);
const root=new Node('div');ctx.renderAnchorStopPicker(trip,trip.days[0],root);
const all=n=>[n,...n.children.flatMap(all)];
(async()=>{
 const disclosure=root.children[0];assert.equal(disclosure.tagName,'details');assert.equal(disclosure.open,false);assert.equal(disclosure.children[0].textContent,'添加住宿 / 口岸');
 const nodes=all(root),select=nodes.find(n=>n.className==='day-point-select'),minutes=nodes.find(n=>n.className==='anchor-dwell'),position=nodes.find(n=>n.className==='anchor-position'),purpose=nodes.find(n=>n.className==='hotel-stay-kind'),search=nodes.find(n=>n.className==='anchor-stop-search');
 const buttons=nodes.filter(n=>n.tagName==='button');assert.equal(buttons.length,1);assert.equal(buttons[0].textContent,'添加到行程');
 assert.equal(minutes.value,60);assert.equal(purpose.value,'rest');
 select.value='current-hotel';await buttons[0].events.click();assert.equal(ctx.calls[0][4],'rest');assert.equal(ctx.calls[0][3],60);
 purpose.value='overnight';minutes.value='480';position.value='1';await buttons[0].events.click();assert.equal(ctx.calls[1][4],'overnight');assert.equal(ctx.calls[1][3],480);
 search.value='机场';search.events.input();assert.ok(select.children.some(n=>n.textContent.includes('机场')));assert.ok(!select.children.some(n=>n.textContent.includes('酒店')));
 select.value='arrival_anchor';select.events.change();assert.equal(purpose.parentNode.hidden,true);minutes.value=0;await buttons[0].events.click();
 search.value='';search.events.input();select.value='departure_anchor';await buttons[0].events.click();assert.deepEqual(ctx.calls.map(c=>c[1].type),['hotel','hotel','arrival_anchor','departure_anchor']);assert.equal(ctx.calls[2][4],null);
 console.log('Anchor picker: collapsed search, one action, rest/overnight, and both hub types passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
