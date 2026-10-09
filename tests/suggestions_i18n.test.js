"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const web = path.join(__dirname, '../modules/web_workbench/web');
class Node {
  constructor(tag, text) { this.nodeType=text===undefined?1:3;this.tagName=tag;this.nodeValue=text;this.childNodes=[];this.attrs={};this.parentElement=null;this.dataset={}; }
  append(...nodes) {for (const node of nodes) {this.childNodes.push(node);node.parentElement=this;}return nodes[0];}
  replaceChildren(...nodes) {this.childNodes=[];this.append(...nodes);}
  get children() {return this.childNodes.filter(node=>node.nodeType===1);}
  get textContent() {return this.nodeType===3 ? this.nodeValue : this.childNodes.map(node=>node.textContent).join('');}
  set textContent(text) {if(this.nodeType===3)this.nodeValue=text;else this.replaceChildren(new Node('',String(text)));}
  addEventListener() {}
  getAttribute(key) {return this.attrs[key] ?? null;}
  hasAttribute(key) {return key in this.attrs;}
  setAttribute(key,value) {this.attrs[key]=value;}
}
const root = new Node('HTML'), body=root.append(new Node('BODY'));
const context={document:{documentElement:root,body,getElementById:()=>null},console};
context.window=context;vm.createContext(context);
for (const file of ['i18n_catalog.js','poi_i18n_catalog.js','suggestions_i18n.js','i18n.js']) {
  const target=path.join(web,file);
  if(fs.existsSync(target)) vm.runInContext(fs.readFileSync(target,'utf8'),context);
}
const api=context.IRLanguage;
const ticketBody='若取消这次付费游览，每人可减少这次计入的门票估算；请在当天行程自行调整。';
const transitBody='到当天交通卡选择公共交通；切换后重新计算行程时间。费用来自当前可用方案。';
const budgetSamples=[
  `评估减少 CustomMuseum 的付费游览，每人可省 ¥60.00。${ticketBody}`,
  `评估减少 我的自定义博物馆 的付费游览，每人可省 ¥60.00–¥80.00。${ticketBody}`,
  `Day 3 第 2 段交通可考虑公共交通，每人可省 ¥15.50–¥30.00，耗时增加 12.5 分钟。${transitBody}`,
  `Day 3 第 4 段交通（返程 / 终点）可考虑公共交通，每人可省 ¥15.50，耗时减少 2 分钟。${transitBody}`,
  '住宿每晚人均目标，每人可省 ¥350.00：¥100.00。这是在其他支出保持不变时的预算目标；请核实实际可选价格。住宿目标按每人分摊后的费用计算。',
  '餐饮每日人均目标，每人可省 ¥150.00：¥50.00。这是其他支出保持不变时的每日餐饮预算目标，可在费用设置中按天调整。',
  '餐饮每日人均目标，每人可省 ¥250.00：¥0.00。其他支出已超过预算，即使此项降至 0 仍需同时压缩其他费用；这不是可单独达成的目标。',
  '需要压缩支出或调整每人预算，保守估计需减少 ¥1,230.50 / 人。若保留当前安排，可参考完整费用估算区间调整每人预算。',
];
const reminderSamples=[
  '预计17:30到达；建议18:00以后到达，方便观看夜景。 亮灯时段：18:00–22:00。',
  '计划到达时间偏早；建议傍晚以后到达，方便观看夜景。 亮灯时段：18:00起。',
  '预计23:00到达；亮灯22:00结束，可能看不到夜景。建议提前前往或调整日期。',
  '到达时间偏晚；亮灯当晚结束，可能看不到夜景。建议提前前往或调整日期。',
  'CustomMuseum → CustomPark：交通约45分钟，直线距离约12.5公里。可以将其中一个景点换到其他天，减少往返。',
  '相邻景点之间交通约待确认分钟。可以将其中一个景点换到其他天，减少往返。',
  '这一天有3个历史人文景点。可以搭配其他类别，让安排更丰富。',
  '这一天有多个个同类景点。可以搭配其他类别，让安排更丰富。',
  '周一闭馆，按当前安排可能无法入内。请选择保留或移除。',
  '周一闭馆，按当前安排可能无法入内。 你已选择保留，闭馆风险仍然存在。',
  '有暂停开放提醒：计划当天可能暂停开放，请核对官方公告。请选择保留或移除。',
  '预计17:30到达；建议18:00以后到达，方便观看夜景。 请重新检查行程，确认这条提醒对应的日期和景点。',
  '2处安排需要你处理',
  '有3处开放信息需要出发前核实',
  '2条安排建议 · 3处开放信息待核实。补齐下方信息后再检查。',
  '0条安排建议 · 2处开放信息待核实。请查看下方提醒。',
  '第3天（2026-10-08）还有2段交通时间未确定，暂时算不出完整的到达时间。',
  '计算第3天交通',
  '闭馆日期：没有适用于出行日期的资料，暂时无法给出结论。',
];
const recommendationSamples=[
  '推荐理由：匹配所选兴趣；按每日起终点及区域距离安排顺序；已预留停留、交通估算及休息时间；参考亮灯窗口安排晚间游玩',
  '提示：开放与闭馆资料待核验，不能保证入场。；此景点需要预约，请自行核验预约资格及名额。',
  '第 2 天安排 2 个景点：已知闭馆、开放时段、停留或出行时间不足，未为填满数量重复添加。',
  '第 3 天未新增：未安排：可用且未重复的候选不足。',
];
const pois=['shanghai_pois_v1.json','shanghai_pois_v2.json'].flatMap(file=>JSON.parse(fs.readFileSync(path.join(__dirname,'../modules/trip_engine/data',file),'utf8')));
for (const category of new Set(pois.map(poi=>poi.category.label_zh))) {
  reminderSamples.push(`这一天有3个${category}景点。可以搭配其他类别，让安排更丰富。`);
}
// Render real backend-shaped suggestions through the production DOM renderer.
const budgetRoot=body.append(new Node('SECTION'));
context.element=(tag,className,text)=>{const node=new Node(tag.toUpperCase());node.className=className;if(text)node.textContent=text;return node;};
context.$=id=>id==='budget-assessment'?budgetRoot:null;
context.state={pois,trip:{trip_id:'translation-fixture',days:[],budget_assessment:{complete:true,status:'over_budget',total:{min_cents:100000,max_cents:100000},defaults:{lodging_nights:[],dates:[]},suggestions:[
  {title:'评估减少 CustomMuseum 的付费游览',body:ticketBody,savings_min_cents:6000,savings_max_cents:8000},
  {title:'Day 3 第 2 段交通可考虑公共交通',body:transitBody,savings_min_cents:1550,savings_max_cents:3000,extra_minutes:12.5},
  {title:'住宿每晚人均目标',body:'这是在其他支出保持不变时的预算目标；请核实实际可选价格。住宿目标按每人分摊后的费用计算。',savings_min_cents:35000,savings_max_cents:35000,target_cents:10000},
  {title:'需要压缩支出或调整每人预算',body:'若保留当前安排，可参考完整费用估算区间调整每人预算。',required_reduction_cents:123050},
]}}};
for (const file of ['currency.js','budget_assessment.js','reminders.js']) vm.runInContext(fs.readFileSync(path.join(web,file),'utf8'),context);
context.hhmm=()=> '17:30';context.engineReady=()=>true;
context.actionButton=(text)=>context.element('button','',text);
const textNodes=node=>node.nodeType===3?[node]:node.childNodes.flatMap(textNodes);
const actualAdvice=[];
for (const currency of ['CNY','USD','EUR','GBP','JPY','HKD','AUD','CAD','SGD']) {
  vm.runInContext(`currencyView={code:'${currency}',rate:'7'};`,context);
  context.renderBudgetAssessment();
  const nodes=textNodes(budgetRoot).filter(node=>context.state.trip.budget_assessment.suggestions.some(s=>node.nodeValue.endsWith(s.body)));
  assert.equal(nodes.length,4,'Production budget renderer must emit all four suggestion kinds');
  actualAdvice.push(...nodes.map(node=>node.nodeValue));
}
context.state.trip.days=[{day_index:3,date:'2026-10-08',ordered_stops:[]}];
const notices=[
  {message_key:'rule.lightup.too_early',severity:'soft_warning',message_args:{day_index:3,poi_name:'CustomMuseum',arrival_local:'17:30',T_light:'18:00',light_start:'18:00',light_close:'22:00'}},
  {message_key:'rule.lightup.too_late',severity:'soft_warning',message_args:{day_index:3,poi_name:'CustomMuseum',arrival_local:'23:00',window_close:'22:00'}},
  {message_key:'rule.spread.long_transit',severity:'soft_hint',message_args:{from_name_zh:'CustomMuseum',to_name_zh:'CustomPark',duration_minutes:65,distance_km:18}},
  {message_key:'rule.homogeneous.banner',severity:'soft_hint',message_args:{count:3,category_zh:'自然生态'}},
  {message_key:'rule.closure.confirm',severity:'hard',outcome:'confirmed_proceed',message_args:{weekday:'Monday'}},
  {message_key:'rule.closure.data_unverified',severity:'soft_hint',message_args:{}},
];
actualAdvice.push(...notices.map(notice=>context.reminderModel(notice).body));
const reminderRoot=body.append(new Node('SECTION'));
context.renderTripReminders(reminderRoot,{notices},true);
actualAdvice.push(...textNodes(reminderRoot).map(node=>node.nodeValue));
for (const original of [...budgetSamples,...reminderSamples,...recommendationSamples,...actualAdvice]) {
  const node=body.append(new Node('',original));
  for (const code of ['en','ja','ko']) {
    const translated=api.translate(original,code);
    assert.notEqual(translated,original,`Missing ${code} advice: ${original}`);
    if(code==='en') assert.ok(!/[\u4e00-\u9fff]/.test(translated.replaceAll('我的自定义博物馆','')),`Partial English advice: ${translated}`);
    assert.ok(!/；建议|以后到达|可以将其中一个景点|这一天有|匹配所选兴趣|需要压缩支出|评估减少| 的付费游览|每人可省|保守估计需减少|，耗时/.test(translated),`Untranslated advice clause in ${code}: ${translated}`);
    const actualNumbers=translated.replaceAll('1인당','').replaceAll('1박','').match(/\d+(?:\.\d+)?/g);
    assert.deepEqual(actualNumbers,original.match(/\d+(?:\.\d+)?/g),`Changed numbers in ${code}: ${original}`);
    api.setLanguage(code);assert.equal(node.nodeValue,translated);
  }
  api.setLanguage('zh-CN');assert.equal(node.nodeValue,original,'Chinese original must survive language switching');
}
assert.match(api.translate(budgetSamples[0],'en'),/^Consider reducing paid visits to CustomMuseum, save ¥60\.00 per person\. /);
assert.equal(api.translate('预计17:30到达；建议18:00以后到达，方便观看夜景。','ja'),'到着予定は17:30。夜景を見るには18:00以降の到着をおすすめします。');
assert.equal(api.translate('预计17:30到达；建议18:00以后到达，方便观看夜景。','ko'),'17:30 도착 예정. 야경을 감상하려면 18:00 이후에 도착하세요.');
assert.equal(api.translate('安排建议（3）','ja'),'予定の提案（3）');
assert.equal(api.translate('安排建议（3）','ko'),'일정 제안 (3)');
assert.match(api.translate(budgetSamples[1],'en'),/我的自定义博物馆/,'Unknown user names are preserved');
assert.equal(api.translate('我的自定义博物馆 2026-10-08 18:00','en'),'我的自定义博物馆 2026-10-08 18:00');
assert.equal(api.translate('这一天有3个我写的类别景点。可以搭配其他类别，让安排更丰富。','en').includes('我写的类别'),true);
for(const code of ['en','ja','ko']) {
  assert.ok(!/[\u4e00-\u9fff]/.test(api.translate('¥60.00（USD 汇率待填写）',code)) || code==='ja');
  assert.equal(api.translate('我的博物馆 我的公园 2026-10-08 18:00',code),'我的博物馆 我的公园 2026-10-08 18:00','Category translations must not rewrite personal names');
}
const entries=context.IRLanguageCatalog;
assert.equal(new Set(entries.map(row=>row[0])).size,entries.length,'Supplement must skip existing dictionary keys');
assert.ok(entries.every(row=>row.length===4 && row.every(value=>value.length>0)));
assert.ok(context.IRSupplementalLanguagePatterns.every(([pattern,templates])=>pattern.source.startsWith('^') && pattern.source.endsWith('$') && templates.length===3));
console.log('suggestions i18n: production budget/reminder DOM, nine currencies, 16 categories, en/ja/ko advice and Chinese recovery passed');
