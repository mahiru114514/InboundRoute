"use strict";
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const web = path.join(__dirname, '../modules/web_workbench/web');
const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
assert.ok(html.includes('id="onboarding-open"'), 'The workbench needs a visible guide entry');
const pageIds=[...html.matchAll(/id="([^"]+)"/g)].map(match=>match[1]);
assert.equal(new Set(pageIds).size,pageIds.length,'HTML IDs must be unique');
assert.equal((html.match(/src="\/onboarding\.js/g)||[]).length,1,'Guide script loads once');
assert.ok(html.includes('id="onboarding-chapters"'), 'Detailed guide needs chapter navigation');
assert.equal((html.match(/src="\/onboarding_content\.js/g)||[]).length,1,'Detailed content loads once');
assert.ok(html.indexOf('/onboarding_content.js')<html.indexOf('/i18n.js'),'Detailed dictionary registers before language initialization');
const source = fs.readFileSync(path.join(web, 'onboarding.js'), 'utf8');

function load({store = new Map(), broken = false, language = 'zh-CN'} = {}) {
  const listeners = {};
  let document;
  class Element {
    constructor(id) { this.id=id; this.listeners={}; this.textContent=''; this.disabled=false; this.open=false; this.scrolls=0; this.attrs={}; this.scrollTop=0; }
    setAttribute(k,v) {this.attrs[k]=v;}
    getAttribute(k) {return this.attrs[k];}
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    emit(type) { for (const fn of this.listeners[type] || []) fn({preventDefault(){}}); }
    click() { if (!this.disabled) this.emit('click'); }
    showModal() { this.open=true; this.shows=(this.shows || 0)+1; }
    close() { this.open=false; this.emit('close'); }
    focus() { document.activeElement=this; }
    scrollIntoView() { this.scrolls++; }
  }
  const ids=[...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
  const nodes=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
  document={getElementById:id=>nodes[id] || null, activeElement:nodes['onboarding-open']};
  const ctx={document, console, navigator:{languages:[language]}, localStorage:{
    getItem(k){if(broken)throw Error('storage denied');return store.get(k) || null;},
    setItem(k,v){if(broken)throw Error('storage denied');store.set(k,v);},
  }, addEventListener(type,fn){(listeners[type] ||= []).push(fn);}};
  ctx.window=ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(web,'i18n_catalog.js'),'utf8'),ctx);
  vm.runInContext(fs.readFileSync(path.join(web,'onboarding_content.js'),'utf8'),ctx);
  vm.runInContext(fs.readFileSync(path.join(web,'i18n.js'),'utf8'),ctx);
  // Exercise actual translations without needing a DOM tree / MutationObserver.
  ctx.IRLanguage.setLanguage(language, false);
  vm.runInContext(source,ctx);
  ctx.IROnboarding.init();
  return {nodes,store,ctx,document,language(code){ctx.IRLanguage.setLanguage(code,false);for(const fn of listeners['inboundroute:languagechange'] || [])fn();}};
}

const detailed=load(), guide=detailed.nodes;
assert.equal(new Set(detailed.ctx.IRLanguageCatalog.map(row=>row[0])).size,detailed.ctx.IRLanguageCatalog.length,'Combined guide dictionary keys are unique');
assert.ok(detailed.ctx.IRLanguageCatalog.every(row=>row.length===4 && row.every(text=>text.length>0)),'Detailed text needs all four languages');
for(let chapter=0;chapter<5;chapter++) {
  guide['onboarding-chapter-'+chapter].click();
  assert.equal(guide['onboarding-progress'].textContent,`${chapter+1} / 5`);
  assert.equal(guide['onboarding-chapter-'+chapter].getAttribute('aria-current'),'step');
  for(const id of ['onboarding-example','onboarding-question-1','onboarding-answer-1','onboarding-question-2','onboarding-answer-2',...Array.from({length:4},(_,i)=>'onboarding-howto-'+i)])
    assert.ok(guide[id].textContent.length>0, `Detailed content missing: ${id}`);
  guide['onboarding-faq-1'].open=true;
  guide['onboarding-content'].scrollTop=125;
  for(const code of ['en','ja','ko','zh-CN']) {
    detailed.language(code);
    assert.equal(guide['onboarding-progress'].textContent,`${chapter+1} / 5`);
    assert.equal(guide['onboarding-faq-1'].open,true,'Language switch preserves expanded question');
    assert.equal(guide['onboarding-content'].scrollTop,125,'Language switch preserves scrolling');
    if(code==='en')for(const id of ['onboarding-example','onboarding-question-1','onboarding-answer-1','onboarding-question-2','onboarding-answer-2',...Array.from({length:4},(_,i)=>'onboarding-howto-'+i)])
      assert.ok(!/[\u4e00-\u9fff]/.test(guide[id].textContent), `Untranslated detail: ${guide[id].textContent}`);
  }
  guide['onboarding-chapter-'+((chapter+1)%5)].click();
  assert.equal(guide['onboarding-faq-1'].open,false,'Chapter navigation resets questions');
  assert.equal(guide['onboarding-content'].scrollTop,0,'Chapter navigation starts at top');
}
const first=load(), d=first.nodes;
assert.equal(d['onboarding-dialog'].open,true,'First visit opens automatically');
first.ctx.IROnboarding.init();
assert.equal(d['onboarding-dialog'].shows,1,'Init is idempotent');
assert.equal(d['onboarding-progress'].textContent,'1 / 5');
assert.equal(d['onboarding-prev'].disabled,true);
const heading=d['onboarding-step-title'].textContent;
d['onboarding-prev'].click();
assert.equal(d['onboarding-step-title'].textContent,heading);
d['onboarding-next'].click();
assert.equal(d['onboarding-progress'].textContent,'2 / 5');
d['onboarding-prev'].click();
assert.equal(d['onboarding-progress'].textContent,'1 / 5');
d['onboarding-skip'].click();
assert.equal(d['onboarding-dialog'].open,false);
assert.equal(first.document.activeElement,d['onboarding-open']);
assert.equal(load({store:first.store}).nodes['onboarding-dialog'].open,false,'Skip persists across refresh');
d['onboarding-open'].click();
assert.equal(d['onboarding-dialog'].open,true,'Manual replay always available');
assert.equal(d['onboarding-progress'].textContent,'1 / 5');
for(let i=0;i<4;i++)d['onboarding-next'].click();
assert.equal(d['onboarding-progress'].textContent,'5 / 5');
assert.equal(d['onboarding-next'].textContent,'去设置行程');
d['onboarding-next'].click();
assert.equal(d['onboarding-dialog'].open,false);
assert.equal(d['setup-disclosure'].open,true);
assert.equal(d['setup-panel'].scrolls,1);
assert.equal(first.document.activeElement,d['setup-panel']);
assert.equal(load({store:first.store}).nodes['onboarding-dialog'].open,false,'Completion persists');

const escaped=load();
escaped.nodes['onboarding-dialog'].emit('cancel');
assert.equal(escaped.nodes['onboarding-dialog'].open,false,'Escape dismisses');
assert.equal(load({store:escaped.store}).nodes['onboarding-dialog'].open,false,'Escape persists');
const closed=load();closed.nodes['onboarding-close'].click();
assert.equal(load({store:closed.store}).nodes['onboarding-dialog'].open,false,'Close persists');
const blocked=load({broken:true});
assert.equal(blocked.nodes['onboarding-dialog'].open,true);
assert.doesNotThrow(()=>blocked.nodes['onboarding-skip'].click());
blocked.ctx.IROnboarding.init();
assert.equal(blocked.nodes['onboarding-dialog'].open,false);
blocked.nodes['onboarding-open'].click();
assert.equal(blocked.nodes['onboarding-dialog'].open,true);

const localized=load();
for(const code of ['en','ja','ko','zh-CN']) {
  localized.language(code);
  for(let i=0;i<5;i++) {
    for(const id of ['onboarding-step-title','onboarding-body','onboarding-tip','onboarding-location','onboarding-next']) {
      const text=localized.nodes[id].textContent;
      assert.ok(text.length>0, `${code} ${id} must be populated`);
      if(code==='en')assert.ok(!/[\u4e00-\u9fff]/.test(text), `Untranslated ${text}`);
    }
    if(i<4)localized.nodes['onboarding-next'].click();
  }
  localized.nodes['onboarding-prev'].click();
  const progress=localized.nodes['onboarding-progress'].textContent;
  localized.language(code==='en'?'ja':'en');
  assert.equal(localized.nodes['onboarding-progress'].textContent,progress,'Language switch preserves step');
  localized.nodes['onboarding-skip'].click();localized.nodes['onboarding-open'].click();
}
const app=fs.readFileSync(path.join(web,'app.js'),'utf8');
assert.ok(app.indexOf('IROnboarding.init')>0 && app.indexOf('IROnboarding.init')<app.indexOf('await api('),'Guide initialization precedes network requests');
assert.ok(html.indexOf('/onboarding.js')<html.indexOf('/app.js'));
console.log('onboarding: first visit, persistence, replay, navigation, keyboard dismissal, storage failure, focus and four languages passed');
