const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node {
  constructor(tag,cls='',text=''){Object.assign(this,{tagName:tag,className:cls,textContent:text,children:[],events:{}});}
  append(...nodes){this.children.push(...nodes);}
  addEventListener(name,fn){this.events[name]=fn;}
}
const ctx={state:{pois:[{poi_id:'a',names:{'zh-Hans':'东方明珠',en:'Oriental Pearl Tower'}}],trip:{trip_id:'demo',days:[
  {day_index:2,date:'2026-10-13',ordered_stops:[{poi_id:'a',arrival_at:123,transit_from_previous:null}]}]}},
  element:(...a)=>new Node(...a),hhmm:()=> '14:10',engineReady:()=>true,actionButton:(t,fn)=>Object.assign(new Node('button','',t),{action:fn}),
  api:async()=>({trip:{}}),evaluateTrip:async()=>{},afterTripEdit:async()=>{}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('modules/web_workbench/web/reminders.js','utf8'),ctx);
const light={severity:'soft_warning',message_key:'rule.lightup.too_early',message_args:{day_index:2,date:'2026-10-13',poi_id:'a',arrival_local:'14:10',T_light:'18:30',light_start:'19:00',light_close:'23:00'}};
let model=ctx.reminderModel(light);
assert.ok(model.title.includes('第2天')&&model.title.includes('东方明珠'));
assert.ok(model.body.includes('14:10')&&model.body.includes('18:30')&&model.body.includes('19:00–23:00'));
assert.equal(model.group,'suggest');
const closure={severity:'hard',outcome:'pending',message_key:'rule.closure.confirm',message_args:{notice_id:'rule_01_closure:2:a',poi_name:'Oriental Pearl Tower',weekday:'Monday'}};
assert.ok(ctx.reminderText(closure).includes('东方明珠'));assert.ok(ctx.reminderText(closure).includes('周一'));
const info={severity:'soft_hint',message_key:'rule.closure.data_unverified',message_args:{poi_name:'Oriental Pearl Tower',day_index:2}};
assert.equal(ctx.reminderModel(info).group,'verify');
ctx.state.pois[0].operating_rules={closure_rules:[{reason_en:'Spring Festival closure',reason_zh:'春节暂停开放'}]};
const special={...closure,message_key:'rule.closure.reason',message_args:{...closure.message_args,reason:'Spring Festival closure'}};
assert.ok(ctx.reminderModel(special).body.includes('春节暂停开放'));
const confirmed=ctx.reminderModel({...closure,outcome:'confirmed_proceed'});
assert.ok(confirmed.body.includes('已选择保留')&&!confirmed.body.includes('请选择保留或移除'));
const oldLate=ctx.reminderModel({message_key:'rule.lightup.too_late',message_args:{window_close:'23:00'}});
assert.ok(oldLate.body.includes('重新检查')&&oldLate.body.includes('日期和景点'));
const box=new Node('div');ctx.renderTripReminders(box,{notices:[light,closure],overflow:1,overflow_notices:[info],skipped_rules:[{rule_id:'rule_02_lightup',reason:'missing_route_duration'}]},true);
const allText=n=>[n.textContent,...n.children.flatMap(allText)];const text=allText(box).join('\n');
for(const name of ['需要处理','安排建议','出发前核实','东方明珠','1段交通','计算第2天交通','仍然保留','移除此景点']) assert.ok(text.includes(name),name);
assert.ok(!text.includes('未就地展示')&&!text.includes('非硬')&&!text.includes('Oriental Pearl Tower'));
const hardBox=box.children.flatMap(n=>n.children).find(n=>n.className.includes('reminder-card warning'));
assert.ok(hardBox,'hard conflict remains visible');
const empty=new Node('div');ctx.renderTripReminders(empty,{notices:[],skipped_rules:[{rule_id:'rule_02_lightup',reason:'no_match'}]},true);
assert.ok(allText(empty).join(' ').includes('还不能完整判断'));
(async()=>{
  const requests=[];ctx.api=async(path,options)=>{requests.push({path,options});return {trip:ctx.state.trip};};
  const buttons=hardBox.children.find(n=>n.className==='reminder-actions').children;
  await buttons.find(n=>n.textContent==='仍然保留').action();
  await buttons.find(n=>n.textContent==='移除此景点').action();
  assert.equal(requests[0].options.body.decision,'proceed_anyway');
  assert.ok(requests[0].path.includes('rule_01_closure%3A2%3Aa'));
  assert.equal(requests[1].path,'/api/trips/demo/days/2/stops/a');
  assert.equal(requests[1].options.method,'DELETE');
  console.log('Reminders: Chinese context, actual vs recommended times, groups, overflow, hard actions and incomplete checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
