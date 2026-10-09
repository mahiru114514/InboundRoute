"use strict";
/* View/input currency only. Trip budgets and cost inputs remain integer CNY cents. */
const currencyCodes = ['CNY','USD','EUR','GBP','JPY','HKD','AUD','CAD','SGD'];
const currencyPreferenceKey = 'wb-currency-view-v1';
const currencyMaxCents = 999999999999n;
let currencyView = {code:'CNY',rate:'1',source:'CNY',date:'',source_url:'',cached:false,stale:false};
let currencyRequest = 0;
let currencyInputRevision = 0;
let currencyCanonical = null;
let currencyPendingBudget = null;
let currencyWired = false;

function currencyDecimal(text, places, label) {
  text=String(text).trim();
  if (!new RegExp(`^\\d+(?:\\.\\d{1,${places}})?$`).test(text) || text.length>40) throw new Error(`${label}须为非负金额，最多${places}位小数`);
  const [whole,fraction='']=text.split('.');
  return {numerator:BigInt(whole+fraction),denominator:10n**BigInt(fraction.length)};
}
function currencyRate(value) {
  const rate=currencyDecimal(value,12,'汇率');
  if (rate.numerator<=0n) throw new Error('汇率须为大于 0 的有效数值');
  return rate;
}
function currencyRound(numerator,denominator) { return (numerator+denominator/2n)/denominator; }
function currencyBound(cents) {
  if (cents<0n || cents>currencyMaxCents) throw new Error('每人预算超出允许范围');
  return Number(cents);
}
function currencyCents(value) {
  if (!Number.isSafeInteger(value) || value<0 || value>Number(currencyMaxCents)) throw new Error('金额超出允许范围');
  return BigInt(value);
}
function currencyCurrentRate() {
  if (currencyView.code==='CNY') return {numerator:1n,denominator:1n};
  if (currencyView.rate==null) throw new Error('缺少有效汇率，请更新汇率或手动填写');
  return currencyRate(currencyView.rate);
}
function readCurrencyBudget(text) {
  text=String(text ?? '').trim();
  if (!text) return null;
  const amount=currencyDecimal(text,2,'每人预算'),rate=currencyCurrentRate();
  const identity=currencyCanonical;
  const cents=identity && identity.text===text && identity.code===currencyView.code && identity.rate===currencyView.rate
    ? currencyCents(identity.cents)
    : currencyRound(amount.numerator*100n*rate.numerator,amount.denominator*rate.denominator);
  return {scope:'per_person',currency:'CNY',amount_cents:currencyBound(cents)};
}
function currencyInputText(cents,display=false) {
  const rate=currencyCurrentRate();
  if (display && !Number.isSafeInteger(cents)) throw new Error('金额超出允许范围');
  const base=display?BigInt(cents):currencyCents(cents),negative=base<0n;
  const units=currencyRound((negative?-base:base)*rate.denominator,rate.numerator);
  return `${negative && units!==0n?'-':''}${units/100n}.${String(units%100n).padStart(2,'0')}`;
}
function setCurrencyBudgetInput(cents) {
  const node=$('budget-per-person');if (!node) return;
  currencyInputRevision++;currencyCanonical=null;currencyPendingBudget=null;
  if (cents==null) {node.value='';return;}
  try {
    node.value=currencyInputText(cents);
    currencyCanonical={text:node.value,code:currencyView.code,rate:currencyView.rate,cents,revision:currencyInputRevision};
  } catch (error) {
    node.value='';currencyPendingBudget={cents,revision:currencyInputRevision,text:''};
    currencyHint(error.message);
  }
}
function currencyBudgetForChange() {
  const text=$('budget-per-person')?.value || '';
  try {return {cents:readCurrencyBudget(text)?.amount_cents ?? null,revision:currencyInputRevision,text};}
  catch (_) {return currencyPendingBudget && currencyPendingBudget.revision===currencyInputRevision ? currencyPendingBudget : null;}
}
function formatCurrencyMoney(cents) {
  if (!Number.isSafeInteger(cents)) throw new Error('金额超出允许范围');
  const cny=`¥${(cents/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  if (currencyView.code==='CNY') return cny;
  try {
    const text=currencyInputText(cents,true),[whole,fraction]=text.split('.');
    const grouped=BigInt(whole).toLocaleString('en-US');
    return `${cny}（约 ${currencyView.code} ${whole==='-0'?'-0':grouped}.${fraction}）`;
  } catch (_) {return `${cny}（${currencyView.code} 汇率待填写）`;}
}
function currencySnapshot() {
  const text=$('budget-per-person')?.value || '';
  let identity=null;
  try {const budget=readCurrencyBudget(text);if (budget) identity={budget_cents:budget.amount_cents};} catch (_) {}
  const pending=currencyPendingBudget?.revision===currencyInputRevision?currencyPendingBudget:null;
  return {...currencyView,budget_text:text,unavailable:currencyView.code!=='CNY' && currencyView.rate==null,...identity,...(pending?{pending_budget_cents:pending.cents,pending_text:pending.text}:null)};
}
function applyCurrencySnapshot(snapshot) {
  currencyRequest++;
  if (!snapshot || !currencyCodes.includes(snapshot.code)) return false;
  let rate='1';
  try {if (snapshot.code!=='CNY') {if (snapshot.unavailable===true && snapshot.rate==null) rate=null;else {currencyRate(snapshot.rate);rate=String(snapshot.rate);}}} catch (_) {return false;}
  currencyView={code:snapshot.code,rate,source:snapshot.code==='CNY'?'CNY':String(snapshot.source || 'manual'),date:String(snapshot.date || ''),source_url:String(snapshot.source_url || ''),cached:Boolean(snapshot.cached),stale:Boolean(snapshot.stale)};
  currencyPendingBudget=null;currencyCanonical=null;
  if (rate==null && (snapshot.pending_budget_cents===null || Number.isSafeInteger(snapshot.pending_budget_cents) && snapshot.pending_budget_cents>=0 && snapshot.pending_budget_cents<=Number(currencyMaxCents))) {
    currencyPendingBudget={cents:snapshot.pending_budget_cents,text:String(snapshot.pending_text ?? snapshot.budget_text ?? ''),revision:currencyInputRevision};
  }
  if (Number.isSafeInteger(snapshot.budget_cents) && snapshot.budget_cents>=0 && snapshot.budget_cents<=Number(currencyMaxCents) && typeof snapshot.budget_text==='string') {
    try {currencyDecimal(snapshot.budget_text,2,'每人预算');currencyCanonical={cents:snapshot.budget_cents,text:snapshot.budget_text,code:currencyView.code,rate:currencyView.rate,revision:currencyInputRevision};} catch (_) {}
  }
  currencyControls();if (rate!=null) currencyPersist();currencyRender();
  if (currencyWired && rate==null) {
    const request=currencyRequest;
    // Setup restores its raw budget text synchronously after applying this context.
    Promise.resolve().then(()=>{if (request===currencyRequest) return currencyReference(currencyPendingBudget || currencyBudgetForChange());});
  }
  return true;
}
function currencyHint(message) {const node=$('currency-hint');if (node) node.textContent=message;}
function currencyControls(message='') {
  const select=$('currency-select'),rate=$('currency-rate'),label=$('budget-currency-label');
  if (select) select.value=currencyView.code;
  if (rate) {rate.disabled=currencyView.code==='CNY';rate.value=currencyView.rate ?? '';}
  const refresh=$('currency-refresh');if (refresh) refresh.disabled=currencyView.code==='CNY';
  if (label) {
    const text=`每人预算（${currencyView.code}）`;
    // A span is preferred; tolerate a label wrapper without removing its input.
    const span=label.tagName?.toLowerCase()==='label'?label.querySelector?.('span'):label;
    if (span) span.textContent=text;
  }
  currencyHint(message || (currencyView.code==='CNY'?'金额以人民币计入预算。':currencyView.rate==null?'缺少有效汇率，请更新或手动填写。':currencyView.source==='manual'?'正在使用手动汇率；更新汇率可恢复参考汇率。':`${currencyView.source} · ${currencyView.date || '日期未提供'}${currencyView.stale?' · 缓存已过期，请更新核对':currencyView.cached?' · 缓存参考汇率':''} · 外币金额为近似值。`));
}
function currencyPersist() {try {localStorage.setItem(currencyPreferenceKey,JSON.stringify(currencyView));} catch (_) {}}
function currencyRender() {if (typeof renderBudgetAssessment==='function' && typeof state!=='undefined' && state.trip) renderBudgetAssessment();}
function currencySaveDraft() {if (typeof saveDraft==='function') saveDraft();}
function currencyRestoreBudget(pending) {
  // External trip/draft setters establish a newer known CNY identity. A user
  // input event clears these identities, leaving its foreign text untouched.
  const currentText=$('budget-per-person')?.value || '';
  const canonical=currencyCanonical;
  const currentPending=currencyPendingBudget?.revision===currencyInputRevision?currencyPendingBudget:null;
  const currentCanonical=canonical?.revision===currencyInputRevision && canonical.code===currencyView.code && canonical.text===currentText
    ? {cents:canonical.cents,text:canonical.text,revision:canonical.revision}:null;
  const latest=currentPending || currentCanonical || pending;
  if (latest && latest.revision===currencyInputRevision && currentText===latest.text) setCurrencyBudgetInput(latest.cents);
  currencyPendingBudget=null;
}
async function currencyReference(pending,refresh=false,save=true) {
  const request=++currencyRequest,code=currencyView.code;
  currencyControls('正在获取参考汇率；可手动填写汇率。');
  try {
    const result=await api(`/api/currency-rates?currency=${encodeURIComponent(code)}${refresh?'&refresh=1':''}`);
    if (request!==currencyRequest || currencyView.code!==code) return;
    if (!result || result.currency!==code) throw new Error('返回币种不匹配');
    const raw=typeof result.cny_per_unit==='number' && Number.isFinite(result.cny_per_unit) ? result.cny_per_unit.toFixed(12).replace(/0+$/,'').replace(/\.$/,'') : String(result.cny_per_unit);
    currencyRate(raw);
    currencyView={code,rate:raw,source:String(result.source || '参考汇率'),date:String(result.date || ''),source_url:String(result.source_url || ''),cached:Boolean(result.cached),stale:Boolean(result.stale)};
    currencyRestoreBudget(pending);currencyControls();currencyPersist();currencyRender();if (save) currencySaveDraft();
  } catch (error) {
    if (request!==currencyRequest || currencyView.code!==code) return;
    let retained='可选择人民币，或手动填写有效汇率。';
    if (currencyView.rate!=null) {
      if (currencyView.source==='manual') retained='保留手动汇率；可稍后更新参考汇率。';
      else {
        currencyView={...currencyView,stale:true};currencyPersist();
        retained=`保留 ${currencyView.source} · ${currencyView.date || '日期未提供'} · 参考汇率已过期，请更新核对。`;
      }
    }
    currencyControls(`汇率获取失败：${error.message}。${retained}`);currencyRender();if (save) currencySaveDraft();
  }
}
async function wireCurrency() {
  if (currencyWired || !$('currency-select')) return;
  currencyWired=true;
  $('budget-per-person')?.addEventListener('input',()=>{currencyInputRevision++;currencyCanonical=null;currencyPendingBudget=null;});
  $('currency-select').addEventListener('change',async()=>{
    const code=$('currency-select').value;if (!currencyCodes.includes(code)) return;
    const pending=currencyBudgetForChange();
    if (!pending && ($('budget-per-person')?.value || '').trim()) {
      $('currency-select').value=currencyView.code;
      currencyHint('请先填有效汇率，或清空预算后切换币种。');return;
    }
    currencyRequest++;
    currencyView={code,rate:code==='CNY'?'1':null,source:code==='CNY'?'CNY':'',date:'',source_url:'',cached:false,stale:false};
    currencyCanonical=null;currencyPendingBudget=pending;currencyControls();currencyRender();
    if (code==='CNY') {currencyRestoreBudget(pending);currencyControls();currencyPersist();currencySaveDraft();return;}
    await currencyReference(pending);
  });
  $('currency-rate')?.addEventListener('input',()=>{
    if (currencyView.code==='CNY') return;
    const pending=currencyBudgetForChange(),text=$('currency-rate').value.trim();currencyRequest++;
    currencyCanonical=null;currencyPendingBudget=pending;currencyView={...currencyView,rate:null,source:'manual',date:'',source_url:'',cached:false,stale:false};
    try {currencyRate(text);currencyView.rate=text;currencyRestoreBudget(pending);currencyControls();currencyPersist();}
    catch (error) {currencyHint(`汇率无效：${error.message}。请填写有效汇率，或选择人民币。`);}
    currencyRender();currencySaveDraft();
  });
  $('currency-refresh')?.addEventListener('click',async()=>{
    if (currencyView.code==='CNY') return;
    await currencyReference(currencyBudgetForChange(),true);
  });
  let preference=null,invalid=false;
  try {const saved=localStorage.getItem(currencyPreferenceKey);if (saved) {preference=JSON.parse(saved);if (preference.code!=='CNY') currencyRate(preference.rate);invalid=!applyCurrencySnapshot(preference);}} catch (_) {invalid=true;}
  currencyControls(invalid?'已保存的币种设置无效，已使用人民币；可重新选择币种和填写汇率。':'');
  if (preference && !invalid && currencyView.code!=='CNY' && currencyView.source!=='manual') await currencyReference(currencyBudgetForChange(),false,false);
}
