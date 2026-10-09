const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Node {
  constructor(value='') { this.value=value;this.textContent='';this.events={}; }
  addEventListener(name, fn) { this.events[name]=fn; }
  fire(name) { return this.events[name]?.({target:this}); }
}
function harness(preference=null) {
  const nodes=Object.fromEntries(['currency-select','currency-rate','currency-refresh','currency-hint','budget-per-person','budget-currency-label'].map(id=>[id,new Node(id==='currency-select'?'CNY':'')]));
  const requests=[];let renders=0,draftSaves=0;
  const ctx={ $:id=>nodes[id],state:{trip:{trip_id:'t'}},renderBudgetAssessment:()=>{renders++;},
    localStorage:{getItem:()=>preference,setItem:()=>{}},saveDraft:()=>{draftSaves++;},
    api:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject})) };
  vm.createContext(ctx);
  const path='modules/web_workbench/web/currency.js';
  vm.runInContext(fs.existsSync(path)?fs.readFileSync(path,'utf8'):'',ctx);
  return {ctx,nodes,requests,get renders(){return renders;},get draftSaves(){return draftSaves;}};
}
const rate=(currency,cny_per_unit)=>({currency,cny_per_unit,date:'2026-10-07',source:'官方参考',source_url:'https://example.org/rates',cached:false,stale:false});
const plain=value=>JSON.parse(JSON.stringify(value));
(async()=>{
  let h=harness();assert.equal(typeof h.ctx.wireCurrency,'function','currency controls must expose their wiring helper');
  await h.ctx.wireCurrency();assert.equal(h.requests.length,0,'CNY boot does not fetch');
  assert.equal(h.ctx.readCurrencyBudget(''),null);assert.equal(h.ctx.readCurrencyBudget('0').amount_cents,0);
  for (const invalid of ['-1','NaN','Infinity','1e3','1.001','.1','1.','+1']) assert.throws(()=>h.ctx.readCurrencyBudget(invalid));
  assert.equal(h.ctx.readCurrencyBudget('9999999999.99').amount_cents,999999999999);
  assert.throws(()=>h.ctx.readCurrencyBudget('10000000000'));
  h.ctx.setCurrencyBudgetInput(10001);
  h.nodes['currency-select'].value='USD';let pending=h.nodes['currency-select'].fire('change');
  assert.match(h.requests[0].url,/currency=USD/);h.requests[0].resolve(rate('USD','7.123456789123'));await pending;
  assert.equal(h.ctx.readCurrencyBudget(h.nodes['budget-per-person'].value).amount_cents,10001,'reformatted canonical cents are never converted twice');
  assert.match(h.ctx.formatCurrencyMoney(10001),/¥100\.01.*USD/);
  assert.match(h.ctx.formatCurrencyMoney(-10001),/-100\.01.*USD -/,'over-budget remaining amounts can be negative');
  assert.match(h.ctx.formatCurrencyMoney(1000000000000),/USD/,'assessment totals can exceed the per-budget input limit');
  h.nodes['budget-per-person'].value='2.01';h.nodes['budget-per-person'].fire('input');
  assert.equal(h.ctx.readCurrencyBudget('2.01').amount_cents,1432,'high precision reference rate rounds once to CNY cents');
  const snap=h.ctx.currencySnapshot();h.ctx.applyCurrencySnapshot({code:'CNY',rate:'1'});h.ctx.applyCurrencySnapshot(snap);
  assert.deepEqual(plain(h.ctx.readCurrencyBudget('2.01')),{scope:'per_person',currency:'CNY',amount_cents:1432});
  h.nodes['currency-rate'].value='0';h.nodes['currency-rate'].fire('input');assert.throws(()=>h.ctx.readCurrencyBudget('1'),/汇率/);assert.match(h.nodes['currency-hint'].textContent,/汇率/);
  h.nodes['currency-rate'].value='8';h.nodes['currency-rate'].fire('input');
  assert.equal(h.ctx.readCurrencyBudget(h.nodes['budget-per-person'].value).amount_cents,1432,'a temporary invalid rate keeps the last known CNY budget');
  h.nodes['currency-rate'].value='0.000000000001';h.nodes['currency-rate'].fire('input');assert.equal(h.ctx.readCurrencyBudget('0.01').amount_cents,0);
  h.nodes['currency-rate'].value='999999999999';h.nodes['currency-rate'].fire('input');assert.throws(()=>h.ctx.readCurrencyBudget('9999999999.99'),/范围/);
  for (const invalid of ['NaN','Infinity','-1','0','1e2','1.1234567891234']) {h.nodes['currency-rate'].value=invalid;h.nodes['currency-rate'].fire('input');assert.throws(()=>h.ctx.readCurrencyBudget('1'));}

  h=harness();await h.ctx.wireCurrency();h.ctx.setCurrencyBudgetInput(70000);
  h.nodes['currency-select'].value='USD';const first=h.nodes['currency-select'].fire('change');
  const pendingDraft=h.ctx.currencySnapshot(),restored=harness();await restored.ctx.wireCurrency();
  assert.equal(restored.ctx.applyCurrencySnapshot(pendingDraft),true,'an unresolved draft keeps its foreign currency and explicitly missing rate');
  restored.nodes['budget-per-person'].value=pendingDraft.budget_text;
  assert.throws(()=>restored.ctx.readCurrencyBudget(pendingDraft.budget_text),/汇率/);
  await Promise.resolve();assert.equal(restored.requests.length,1,'unresolved draft retries reference rate after setup can restore its input');
  restored.requests[0].resolve(rate('USD','7'));await new Promise(setImmediate);
  assert.equal(restored.nodes['budget-per-person'].value,'100.00');assert.equal(restored.ctx.readCurrencyBudget('100.00').amount_cents,70000);
  const offlineDraft=harness();await offlineDraft.ctx.wireCurrency();offlineDraft.ctx.applyCurrencySnapshot(pendingDraft);offlineDraft.nodes['budget-per-person'].value=pendingDraft.budget_text;
  await Promise.resolve();offlineDraft.requests[0].reject(new Error('offline'));await new Promise(setImmediate);
  assert.equal(offlineDraft.nodes['budget-per-person'].value,'700.00');assert.equal(offlineDraft.ctx.currencySnapshot().pending_budget_cents,70000);
  offlineDraft.nodes['currency-rate'].value='7';offlineDraft.nodes['currency-rate'].fire('input');
  assert.equal(offlineDraft.ctx.readCurrencyBudget(offlineDraft.nodes['budget-per-person'].value).amount_cents,70000);
  h.nodes['currency-select'].value='EUR';const second=h.nodes['currency-select'].fire('change');
  h.requests[1].resolve(rate('EUR','8'));await second;h.requests[0].resolve(rate('USD','7'));await first;
  assert.equal(h.ctx.currencySnapshot().code,'EUR');assert.equal(h.nodes['budget-per-person'].value,'87.50');
  h.nodes['currency-refresh'].fire('click');h.nodes['currency-rate'].value='9';h.nodes['currency-rate'].fire('input');
  h.requests[2].resolve(rate('EUR','8'));await Promise.resolve();await Promise.resolve();
  assert.equal(h.ctx.currencySnapshot().rate,'9','manual rate supersedes pending refresh');
  assert.equal(h.ctx.currencySnapshot().source,'manual');
  const refresh=h.nodes['currency-refresh'].fire('click');
  h.nodes['budget-per-person'].value='33.33';h.nodes['budget-per-person'].fire('input');
  h.requests[3].resolve(rate('EUR','8'));await refresh;
  assert.equal(h.nodes['budget-per-person'].value,'33.33','reference refresh does not overwrite new budget text');
  assert.equal(h.ctx.readCurrencyBudget('33.33').amount_cents,26664);
  const draft=h.ctx.currencySnapshot();h.ctx.setCurrencyBudgetInput(88888);const canonical=h.nodes['budget-per-person'].value;const precise=h.ctx.currencySnapshot();
  h.ctx.applyCurrencySnapshot(draft);h.ctx.applyCurrencySnapshot(precise);h.nodes['budget-per-person'].value=canonical;
  assert.equal(h.ctx.readCurrencyBudget(canonical).amount_cents,88888,'draft rate context retains cent identity');

  h=harness(JSON.stringify({code:'USD',rate:'garbage',source:'manual'}));await h.ctx.wireCurrency();
  assert.equal(h.ctx.currencySnapshot().code,'CNY','invalid cached preference cannot create a valid foreign rate');
  assert.match(h.nodes['currency-hint'].textContent,/无效/);
  h.nodes['currency-select'].value='JPY';const failed=h.nodes['currency-select'].fire('change');h.requests[0].reject(new Error('offline'));await failed;
  assert.throws(()=>h.ctx.readCurrencyBudget('100'),/汇率/);assert.match(h.nodes['currency-hint'].textContent,/手动/);
  h.nodes['budget-per-person'].value='100';h.nodes['budget-per-person'].fire('input');
  h.nodes['currency-select'].value='CNY';await h.nodes['currency-select'].fire('change');assert.equal(h.nodes['budget-per-person'].value,'100','unknown foreign input remains intact when conversion is impossible');
  assert.equal(h.nodes['currency-select'].value,'JPY');assert.match(h.nodes['currency-hint'].textContent,/清空预算后切换/);
  h.nodes['budget-per-person'].value='';h.nodes['budget-per-person'].fire('input');h.nodes['currency-select'].value='CNY';await h.nodes['currency-select'].fire('change');
  assert.equal(h.ctx.readCurrencyBudget('100').amount_cents,10000);
  assert.ok(h.renders>0);
  h=harness(JSON.stringify({code:'USD',rate:'7',source:'官方参考',date:'2026-10-01',stale:true}));
  const boot=h.ctx.wireCurrency();assert.equal(h.requests.length,1);h.requests[0].resolve({...rate('USD','7.2'),cached:true,stale:true});await boot;
  assert.equal(h.draftSaves,0,'boot preference refresh cannot overwrite an existing setup draft before boot restores it');
  assert.match(h.nodes['currency-hint'].textContent,/2026-10-07.*缓存已过期/);
  h.ctx.applyCurrencySnapshot({code:'USD',rate:'7',source:'官方参考',date:'2026-10-01',stale:false});h.ctx.setCurrencyBudgetInput(70000);
  const oldText=h.nodes['budget-per-person'].value,oldRateRefresh=h.nodes['currency-refresh'].fire('click');
  h.requests[1].reject(new Error('offline'));await oldRateRefresh;
  assert.equal(h.ctx.currencySnapshot().rate,'7');assert.equal(h.ctx.currencySnapshot().stale,true,'a failed refresh marks the retained reference rate stale');
  assert.equal(h.nodes['budget-per-person'].value,oldText);assert.equal(h.ctx.readCurrencyBudget(oldText).amount_cents,70000);
  assert.match(h.nodes['currency-hint'].textContent,/失败.*官方参考.*2026-10-01.*过期/,'a retained reference exposes its source, old date and stale state after failure');
  h.nodes['currency-rate'].value='7.2';h.nodes['currency-rate'].fire('input');
  const manualText=h.nodes['budget-per-person'].value,manualRefresh=h.nodes['currency-refresh'].fire('click');h.requests[2].reject(new Error('offline'));await manualRefresh;
  assert.equal(h.ctx.currencySnapshot().rate,'7.2');assert.equal(h.ctx.currencySnapshot().stale,false);
  assert.equal(h.nodes['budget-per-person'].value,manualText);assert.match(h.nodes['currency-hint'].textContent,/失败.*保留手动汇率/);
  const recovered=h.nodes['currency-refresh'].fire('click');h.requests[3].resolve(rate('USD','7.3'));await recovered;assert.equal(h.ctx.currencySnapshot().stale,false);
  h=harness();await h.ctx.wireCurrency();h.ctx.setCurrencyBudgetInput(70000);h.nodes['currency-select'].value='USD';const resetRequest=h.nodes['currency-select'].fire('change');
  h.ctx.setCurrencyBudgetInput(null);h.ctx.currencyControls();
  assert.equal(h.ctx.currencySnapshot().pending_budget_cents,undefined,'resetting budget clears pending CNY identity');
  h.requests[0].resolve(rate('USD','7'));await resetRequest;
  assert.equal(h.nodes['budget-per-person'].value,'','a reference request begun before reset cannot restore cleared budget');
  assert.equal(h.ctx.currencySnapshot().code,'USD');assert.equal(h.nodes['currency-select'].value,'USD');assert.equal(h.ctx.readCurrencyBudget(''),null);
  h=harness();await h.ctx.wireCurrency();h.ctx.setCurrencyBudgetInput(70000);h.nodes['currency-select'].value='USD';const loadingTrip=h.nodes['currency-select'].fire('change');
  h.ctx.setCurrencyBudgetInput(90000);assert.equal(h.nodes['budget-per-person'].value,'');
  h.requests[0].resolve(rate('USD','7'));await loadingTrip;
  assert.equal(h.ctx.readCurrencyBudget(h.nodes['budget-per-person'].value)?.amount_cents,90000,'a trip loaded while first rate is unavailable retains the latest known CNY cents');
  h.ctx.setCurrencyBudgetInput(70000);const collisionRefresh=h.nodes['currency-refresh'].fire('click');h.ctx.setCurrencyBudgetInput(70001);
  assert.equal(h.nodes['budget-per-person'].value,'100.00','different canonical cents can share rounded foreign text');
  h.requests[1].resolve(rate('USD','8'));await collisionRefresh;
  assert.equal(h.ctx.readCurrencyBudget(h.nodes['budget-per-person'].value).amount_cents,70001,'refresh preserves latest external budget even when its previous foreign display collides');
  h=harness();h.ctx.localStorage.getItem=()=>{throw new Error('denied');};h.ctx.localStorage.setItem=()=>{throw new Error('denied');};await h.ctx.wireCurrency();assert.equal(h.ctx.readCurrencyBudget('1').amount_cents,100);
  console.log('Currency UI: exact cents, input validation, asynchronous ordering, manual overrides, draft context and failures passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
