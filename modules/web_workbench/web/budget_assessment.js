/* All amounts entered here are estimates in CNY; blank means unknown. */
let budgetEditorTrip = null;
let budgetEditorDirty = false;
let budgetEditorDetails = null;
let budgetSourcesDetails = null;
function costMoney(value) {
  const text = String(value).trim();
  if (!text) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error('费用请输入非负金额，最多两位小数');
  const [whole, fraction=''] = text.split('.');
  const cents = Number(whole)*100 + Number(fraction.padEnd(2,'0'));
  if (!Number.isSafeInteger(cents) || cents > 999999999999) throw new Error('费用金额超出范围');
  return cents;
}
function budgetMoney(cents) { return typeof formatCurrencyMoney==='function' ? formatCurrencyMoney(cents) : `¥${(cents/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})}`; }
function budgetRange(low,high) { return low === high ? budgetMoney(low) : `${budgetMoney(low)}–${budgetMoney(high)}`; }
function renderBudgetAssessment() {
  const root = $('budget-assessment'); if (!root) return;
  const trip = state.trip;
  if (budgetEditorTrip !== trip?.trip_id) { budgetEditorDirty=false;budgetEditorDetails=null;budgetSourcesDetails=null;budgetEditorTrip=trip?.trip_id; }
  const summary=$('budget-summary');
  root.replaceChildren();
  root.append(element('h3','','每人整趟费用评估'));
  if (!trip) { if (summary) summary.textContent='费用评估 · 保存行程后可评估';root.append(element('p','hint','保存行程后可填写费用并评估预算。'));return; }
  const assessment = trip.budget_assessment;
  if (!assessment) { if (summary) summary.textContent='费用评估 · 评估待加载';root.append(element('p','hint','请重启本地服务以加载费用评估。'));return; }
  const total = assessment.total;
  const labels={no_budget:'尚未设置每人预算',incomplete:'费用待补充',over_budget:'已超出预算',at_risk:'费用区间可能超出预算',within_budget:'估算费用在预算内'};
  if (assessment.stale && assessment.status==='over_budget') labels.over_budget='已填费用估算超出预算，需核对';
  if (summary) summary.textContent=`${assessment.complete?'预计费用':'已计入费用'} ${budgetRange(total.min_cents,total.max_cents)} / 人 · ${labels[assessment.status] || assessment.status}${assessment.missing?.length?` · 待补充 ${assessment.missing.length} 项`:''}`;
  root.append(element('p',assessment.status==='over_budget' || assessment.status==='at_risk'?'warning':'hint',
    `${assessment.complete?'预计费用':'已计入费用'}：${budgetRange(total.min_cents,total.max_cents)} / 人 · ${labels[assessment.status] || assessment.status}`));
  if (assessment.budget_cents != null) root.append(element('p','hint',`预算 ${budgetMoney(assessment.budget_cents)} / 人${assessment.complete && assessment.remaining ? ` · 余额 ${budgetRange(assessment.remaining.min_cents,assessment.remaining.max_cents)}`:''}。价格为估算，请核实实际报价。`));
  for (const category of Object.values(assessment.categories || {})) root.append(element('p','',`${category.label || category.name}：${budgetRange(category.min_cents,category.max_cents)}${category.complete?'':' · 待补充'}`));
  const sourcesOpen=Boolean(budgetSourcesDetails?.open);
  const breakdown=element('details','');breakdown.open=sourcesOpen;budgetSourcesDetails=breakdown;breakdown.append(element('summary','','查看费用明细和来源'));
  const sources={user:'用户估算',reference_price:'自动参考价',user_percentage:'备用金比例',same_place:'同地点无需交通',amap:'高德路线报价',tencent:'腾讯路线报价',baidu:'百度路线报价',curated:'已核实路线参考价',manual:'手工路线报价'};
  function appendSources(parent,urls=[]) {
    for (const [i,url] of urls.entries()) if (/^https:\/\//.test(url)) {
      const link=element('a','',` 来源${i+1}`);link.href=url;link.target='_blank';link.rel='noopener noreferrer';parent.append(link);
    }
  }
  for (const line of assessment.lines || []) {
    const row=element('p','hint',`${line.label}：${budgetRange(line.min_cents,line.max_cents)} / 人 · ${sources[line.source] || line.source}${line.researched_at?`（查询于 ${line.researched_at}）`:''}`);
    appendSources(row,line.sources);breakdown.append(row);
    if (line.reference_note) breakdown.append(element('p','hint',line.reference_note));
  }
  root.append(breakdown);
  for (const assumption of assessment.assumptions || []) root.append(element('p','hint',assumption));
  for (const notice of assessment.price_notices || []) {
    const row=element('p','warning',notice.message);appendSources(row,notice.sources);root.append(row);
  }
  if (assessment.stale) root.append(element('p','warning','行程已改变，请核对住宿晚数、门票和交通费用后重新保存。'));
  for (const missing of assessment.missing || []) root.append(element('p','warning',`待补充：${missing.message}`));
  for (const suggestion of assessment.suggestions || []) {
    let text = suggestion.title || '';
    if (suggestion.savings_min_cents != null) text += `，每人可省 ${budgetRange(suggestion.savings_min_cents,suggestion.savings_max_cents)}`;
    if (suggestion.target_cents != null) text += `：${budgetMoney(suggestion.target_cents)}`;
    if (suggestion.required_reduction_cents != null) text += `，保守估计需减少 ${budgetMoney(suggestion.required_reduction_cents)} / 人`;
    if (suggestion.extra_minutes != null) text += `，耗时${suggestion.extra_minutes>=0?'增加':'减少'} ${Math.abs(suggestion.extra_minutes)} 分钟`;
    root.append(element('p','hint',`${text}。${suggestion.body || ''}`));
  }
  if (budgetEditorDirty && budgetEditorDetails) {
    root.append(element('p','warning','费用修改尚未保存。行程如有变化，请核对上述最新评估和费用后保存。'),budgetEditorDetails);return;
  }
  const wasOpen=budgetEditorDetails?.open;
  const details=element('details','');details.open=Boolean(wasOpen);budgetEditorDetails=details;
  details.append(element('summary','','填写 / 核对费用（人民币）'));root.append(details);
  details.append(element('p','hint','加入景点和酒店后自动计入参考费用。门票按成人基础参考价估算，儿童、学生等优惠请手填人均金额。门票留空沿用参考价，找不到价格时待补充；手填金额优先，填 0 表示免费或不发生。住宿、打车按实际人数分摊；门票按每次停靠计入，重复使用同一张票的停靠请填 0。调整建议不会自动改变行程。'));
  const input=trip.cost_inputs || {}, fields={}, tickets={}, meals={};
  function field(parent,label,key,value,kind='money') {
    const wrap=element('label','');wrap.append(element('span','',kind==='money'?`${label}（人民币元）`:label));
    const node=element('input','');node.type=kind==='text'?'text':kind==='date'?'date':'number';node.dataset.costField=key;
    node.value=value==null?'':kind==='money'?(value/100).toFixed(2):String(value);
    if (node.type==='number') {node.min='0';node.step=kind==='money'?'0.01':'1';}
    node.addEventListener('input',()=>{budgetEditorDirty=true;});wrap.append(node);parent.append(wrap);return node;
  }
  const grid=element('div','form-grid');details.append(grid);
  for (const [key,label,kind] of [['travelers','实际同行人数（住宿未填按 1 人估算）','int'],['lodging_rooms','自动住宿房间数（未填按 1 间）','int'],['taxi_vehicles','每段打车车辆数','int'],['intercity_cents','往返机票 / 跨城交通（每人合计）','money'],['meal_daily_cents','餐饮（每人每天）','money'],['extras_cents','购物 / 其他（每人合计）','money'],['contingency_percent','备用金比例（%）','int']]) fields[key]=field(grid,label,key,input[key] ?? (key==='contingency_percent'?0:key==='lodging_rooms'?1:null),kind);
  details.append(element('h4','','实际住宿晚数'));
  const modeWrap=element('label','');const autoMode=element('input','');autoMode.type='checkbox';autoMode.dataset.costField='automatic_lodging';autoMode.checked=input.lodging_nights==null;
  modeWrap.append(autoMode,element('span','','自动按行程酒店和晚数计费（取消勾选可手填房晚及房价）'));details.append(modeWrap);
  const nightsRoot=element('div','');details.append(nightsRoot);const nights=[];
  function addNight(night={}) {
    const row=element('div','form-grid'), record={};nightsRoot.append(row);
    record.date=field(row,'入住日期','night_date',night.date,'date');record.hotel_name=field(row,'酒店名称','hotel_name',night.hotel_name,'text');
    record.rooms=field(row,'房间数','rooms',night.rooms,'int');record.room_price_cents=field(row,'每间房 / 每晚','room_price_cents',night.room_price_cents);
    for (const node of Object.values(record)) node.disabled=autoMode.checked;
    if (night.reference_price) {
      const ref=night.reference_price;record.room_price_cents.placeholder=`参考 ${budgetRange(ref.min_cents,ref.max_cents)}`;
      row.append(element('p','hint',`${night.hotel_name} 每间每晚参考 ${budgetRange(ref.min_cents,ref.max_cents)}；自动模式保留区间，手动模式请填实际房价。`));
    }
    record.removed=false;const remove=element('button','secondary','移除此晚');remove.type='button';remove.addEventListener('click',()=>{record.removed=true;row.hidden=true;budgetEditorDirty=true;});row.append(remove);nights.push(record);
    record.remove=remove;remove.disabled=autoMode.checked;
  }
  for (const night of input.lodging_nights || assessment.defaults.lodging_nights || []) addNight(night);
  const add=element('button','secondary','增加住宿晚数');add.type='button';add.addEventListener('click',()=>{addNight({date:assessment.defaults.dates[0],rooms:1});budgetEditorDirty=true;});details.append(add);
  add.disabled=autoMode.checked;
  autoMode.addEventListener('change',()=>{
    budgetEditorDirty=true;add.disabled=autoMode.checked;
    for (const night of nights) for (const key of ['date','hotel_name','rooms','room_price_cents','remove']) night[key].disabled=autoMode.checked;
  });
  details.append(element('p','hint','自动模式按行程前 N−1 晚计费，酒店继承、换酒店和改日期后自动更新；途中酒店停靠不会重复计算房费。跨零点抵达、提前入住或延住请取消自动模式，按实际付费夜晚填写。手动模式删除全部住宿行并保存表示没有住宿费用。'));
  details.append(element('h4','','门票及每日餐饮调整'));
  const visits=element('div','form-grid');details.append(visits);
  for (const day of trip.days) {
    meals[day.date]=field(visits,`${day.date} 餐饮 / 人（空白沿用每日金额）`,'meal_override',input.meal_overrides?.[day.date]);
    for (const stop of day.ordered_stops) if (stop.stop_type==='poi' || !stop.stop_type) {
      const id=stop.stop_id || stop.poi_id;
      const poi=(state.pois || []).find(p=>p.poi_id===stop.poi_id);
      tickets[id]=field(visits,`Day ${day.day_index} · ${stop.name_zh || poi?.names?.['zh-Hans'] || stop.poi_id} 门票 / 人`,'ticket',input.ticket_cents?.[id]);
      const reference=assessment.defaults.ticket_prices?.[id];
      tickets[id].placeholder=reference?`留空自动计入 ${budgetRange(reference.min_cents,reference.max_cents)}`:'价格待补充';
    }
  }
  const save=element('button','primary','保存费用并评估');save.type='button';details.append(save);
  function integer(node,label) {if (!String(node.value).trim()) return null; if (!/^\d+$/.test(String(node.value))) throw new Error(`${label}请输入整数`);return Number(node.value);}
  save.addEventListener('click',()=>flowAction(async()=>{
    const costs={};for (const [key,node] of Object.entries(fields)) costs[key]=key.endsWith('_cents')?costMoney(node.value):integer(node,key);
    costs.ticket_cents={};for (const [key,node] of Object.entries(tickets)) costs.ticket_cents[key]=costMoney(node.value);
    costs.meal_overrides={};for (const [key,node] of Object.entries(meals)) if (String(node.value).trim()) costs.meal_overrides[key]=costMoney(node.value);
    costs.lodging_nights=autoMode.checked?null:nights.filter(n=>!n.removed).map(n=>({date:n.date.value,hotel_name:n.hotel_name.value,rooms:integer(n.rooms,'房间数'),room_price_cents:costMoney(n.room_price_cents.value)}));
    state.trip=await api(`/api/trips/${state.trip.trip_id}`,{method:'PATCH',version:state.trip.version,body:{cost_inputs:costs}});
    budgetEditorDirty=false;flow.offline=null;rememberTrip();renderTrip();renderFlow();
  }));
}
