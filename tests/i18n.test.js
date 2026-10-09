"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = path.join(__dirname, '../modules/web_workbench/web/i18n.js');
assert.ok(fs.existsSync(file), 'Language support must exist');
const source = fs.readFileSync(file, 'utf8');
class Node {
  constructor(tag, text) { this.nodeType = text === undefined ? 1 : 3; this.tagName=tag; this.nodeValue=text; this.childNodes=[]; this.attrs={}; this.parentElement=null; }
  append(node) {this.childNodes.push(node);node.parentElement=this;return node;}
  getAttribute(k) {return this.attrs[k] ?? null;}
  setAttribute(k,v) {this.attrs[k]=v;}
  hasAttribute(k) {return k in this.attrs;}
}
function load({saved, languages=['en-US'], broken=false}={}) {
  const root=new Node('HTML'), body=root.append(new Node('BODY'));
  const text=body.append(new Node('', '行程设定'));
  const input=body.append(new Node('INPUT'));input.value='我的自定义酒店';input.setAttribute('placeholder','例如 3000');
  const name=body.append(new Node('SPAN'));name.setAttribute('data-i18n-ignore','');name.append(new Node('', '行程设定'));
  const store=new Map(saved ? [['inboundroute.language',saved]] : []);
  let observer;
  const events=[];
  const document={documentElement:root,body,getElementById:()=>null};
  const context={document,navigator:{languages},localStorage:{getItem:k=>{if(broken)throw Error();return store.get(k);},setItem:(k,v)=>{if(broken)throw Error();store.set(k,v);}},MutationObserver:class {constructor(fn){observer=fn;}observe(){}},console};
  context.window=context;
  context.Event=class {constructor(type){this.type=type;}};
  context.dispatchEvent=event=>events.push(event.type);
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(path.dirname(file),'i18n_catalog.js'),'utf8'),context);
  for (const catalog of ['poi_i18n_catalog.js','suggestions_i18n.js','common_i18n_catalog.js','common_i18n_patterns.js','onboarding_content.js']) {
    const extra=path.join(path.dirname(file),catalog);
    if (fs.existsSync(extra)) vm.runInContext(fs.readFileSync(extra,'utf8'),context);
  }
  vm.runInContext(source,context);
  context.IRLanguage.init();
  return {api:context.IRLanguage,catalog:context.IRLanguageCatalog,root,body,text,input,name,store,events,changed:records=>observer(records)};
}
const a=load();
assert.equal(a.api.language,'en');assert.equal(a.text.nodeValue,'Trip setup');
assert.equal(a.input.value,'我的自定义酒店');assert.equal(a.input.getAttribute('placeholder'),'e.g. 3000');
assert.equal(a.name.childNodes[0].nodeValue,'行程设定');
a.api.setLanguage('ja');assert.equal(a.text.nodeValue,'旅行の設定');
assert.equal(a.events.at(-1),'inboundroute:languagechange');
a.api.setLanguage('ko');assert.equal(a.text.nodeValue,'여행 설정');
a.api.setLanguage('zh-CN');assert.equal(a.text.nodeValue,'行程设定');
assert.equal(a.store.get('inboundroute.language'),'zh-CN');
a.api.setLanguage('en');
const button=a.body.append(new Node('BUTTON'));const dynamic=button.append(new Node('', '加入行程'));
a.changed([{type:'childList',addedNodes:[button]}]);assert.equal(dynamic.nodeValue,'Add to trip');
dynamic.nodeValue='移除';a.changed([{type:'characterData',target:dynamic}]);assert.equal(dynamic.nodeValue,'Remove');
a.api.setLanguage('zh-CN');assert.equal(dynamic.nodeValue,'移除');
assert.equal(load({saved:'ko',languages:['ja-JP']}).api.language,'ko');
assert.equal(load({languages:['fr-FR','ja-JP']}).api.language,'ja');
assert.equal(load({languages:['fr-FR']}).api.language,'en');
assert.equal(load({languages:['zh-TW']}).api.language,'zh-CN');
assert.equal(load({saved:'bad',languages:['ko-KR']}).api.language,'ko');
assert.doesNotThrow(()=>load({broken:true}).api.setLanguage('ja'));
assert.equal(a.api.translate('未知专有名称'),'未知专有名称');
assert.equal(a.api.translate('第 3 天','en'),'Day 3');
assert.equal(a.api.translate('停留 90 分钟','en'),'Stay 90 min');
assert.equal(a.api.translate('公共交通 · 25 分钟','en'),'Public transport · 25 min');
assert.equal(a.api.translate('第 3 天','ja'),'3日目');
assert.equal(a.api.translate('第 3 天','ko'),'3일차');
assert.equal(a.api.translate('计算 Day 3 交通','en'),'Calculate Day 3 transport');
assert.equal(a.api.translate('计算 Day 3 交通','ja'),'3日目の移動を計算');
assert.equal(a.api.translate('每人预算（USD）','en'),'Budget per person (USD)');
assert.equal(a.api.translate('上海 · 2026年10月8日出发 · 5天','en'),'Shanghai · 2026-10-8 · 5 days');
assert.equal(a.api.translate('需提前 3 天预约','en'),'Book 3 days in advance');
assert.equal(a.api.setLanguage('unsupported'),false);
const html=fs.readFileSync(path.join(__dirname,'../modules/web_workbench/web/index.html'),'utf8');
assert.ok(html.includes('id="settings-open"') && html.includes('id="language-select"'));
assert.ok(html.indexOf('/i18n.js') < html.indexOf('/app.js'));
// 确保工作台所有静态中文标签、说明、占位和可访问性属性有英语译文。
const staticText = [...html.matchAll(/>([^<>]+)</g)].map(match=>match[1].trim())
  .concat([...html.matchAll(/(?:aria-label|placeholder|title)="([^"]+)"/g)].map(match=>match[1]));
for (const text of staticText) {
  if (/[\u4e00-\u9fff]/.test(text) && !['简体中文','日本語'].includes(text))
    assert.ok(!/[\u4e00-\u9fff]/.test(a.api.translate(text,'en')),`Missing static translation: ${text}`);
}
const catalogContext={window:{}};vm.createContext(catalogContext);
vm.runInContext(fs.readFileSync(path.join(path.dirname(file),'i18n_catalog.js'),'utf8'),catalogContext);
const entries=catalogContext.window.IRLanguageCatalog;
assert.equal(new Set(entries.map(row=>row[0])).size,entries.length,'Dictionary keys must be unique');
assert.ok(entries.every(row=>row.length===4 && row.every(text=>text.length>0)),'Every entry needs all three translations');
assert.equal(a.api.translate('已计算 2 天、5 个区段。请核实实时交通。','en'),'Calculated 2 days, 5 transfers. Check live transport.');
// 我们自己的 observer 更新不应覆盖原文或继续产生相同写入。
a.api.setLanguage('en');a.changed([{type:'characterData',target:a.text}]);
a.api.setLanguage('ja');a.changed([{type:'characterData',target:a.text}]);
a.api.setLanguage('zh-CN');assert.equal(a.text.nodeValue,'行程设定');
console.log('i18n: language detection, persistence, live updates, original text recovery, user data protection passed');

assert.equal(new Set(a.catalog.map(row=>row[0])).size,a.catalog.length,'Supplementary catalogs must not duplicate dictionary keys');
const pois=['shanghai_pois_v1.json','shanghai_pois_v2.json'].flatMap(name=>JSON.parse(fs.readFileSync(path.join(__dirname,'../modules/trip_engine/data',name),'utf8')));
for (const poi of pois) {
  const original=poi.description_zh;
  for(const code of ['en','ja','ko']) {
    assert.notEqual(a.api.translate(original,code),original,`${poi.poi_id}: introduction remains Chinese in ${code}`);
    if(code==='en')assert.ok(!/[\u4e00-\u9fff]/.test(a.api.translate(original,code)),`${poi.poi_id}: partial English description`);
  }
  assert.equal(a.api.translate(original,'zh-CN'),original);
}
assert.ok(!/id="d-introduction"[^>]*data-i18n-ignore/.test(html),'Detail introduction must participate in language updates');
console.log('i18n: all 45 introductions translated in three languages, original Chinese intact');
assert.ok(!/\(\?:poi-introduction\|/.test(fs.readFileSync('modules/web_workbench/web/runtime.js','utf8')),'The shared element helper must allow introduction translation on all surfaces');
