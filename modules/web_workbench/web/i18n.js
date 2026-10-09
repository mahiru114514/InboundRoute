"use strict";
/* 只本地化显示层：不改变 value、业务数据、DOM 结构、事件或焦点。 */
(() => {
  const languages = [
    {code:'zh-CN', name:'简体中文'}, {code:'en', name:'English'},
    {code:'ja', name:'日本語'}, {code:'ko', name:'한국어'},
  ];
  const storageKey = 'inboundroute.language';
  const entries = window.IRLanguageCatalog || [];
  const dictionaries = Object.fromEntries(['en','ja','ko'].map((code,i) =>
    [code, Object.fromEntries(entries.map(row => [row[0], row[i+1]]))]));
  const escape = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // 单次替换避免日文里相同的汉字被再次翻译。长文案优先于短标签。
  const keys = [...new Set(entries.map(row=>row[0]))].sort((a,b)=>b.length-a.length);
  const matcher = new RegExp(`第\\s*(\\d+)\\s*天|${keys.map(escape).join('|')}`, 'g');
  const originals = new WeakMap();
  const attributes = ['placeholder','aria-label','title'];
  // 数字模板按完整文案匹配，避免外文沿用中文词序。
  const patterns = [
    ...(window.IRSupplementalLanguagePatterns || []),
    [/^计算 Day (\d+) 交通$/, ['Calculate Day $1 transport','$1日目の移動を計算','$1일차 교통 계산']],
    [/^每人预算（([A-Z]{3})）$/, ['Budget per person ($1)','一人あたりの予算（$1）','1인당 예산 ($1)']],
    [/^上海 · (\d{4})年(\d+)月(\d+)日出发 · (\d+)天$/, ['Shanghai · $1-$2-$3 · $4 days','上海 · $1年$2月$3日出発 · $4日間','상하이 · $1-$2-$3 출발 · $4일']],
    [/^(\d+) 天 · 点击修改日期、住宿与偏好$/, ['$1 days · Edit dates, accommodation and preferences','$1日間 · 日程・宿泊先・希望を変更','$1일 · 날짜, 숙소 및 취향 수정']],
    [/^已计算 (\d+) 个区段，展开每日卡片查看和选择交通方式。(.*)$/, ['$1 transfers calculated. Expand a day to view and select transport. $2','$1区間を計算済み。各日を開いて移動手段を選択してください。$2','$1개 구간 계산됨. 날짜를 펼쳐 교통수단을 선택하세요. $2']],
    [/^已计算 (\d+) 天、(\d+) 个区段。(.*)$/, ['Calculated $1 days, $2 transfers. $3','$1日間・$2区間を計算しました。$3','$1일, $2개 구간 계산 완료. $3']],
    [/^Day (\d+)：计算区间 (\d+)\/(\d+)…$/, ['Day $1: calculating transfer $2/$3…','$1日目：区間$2/$3を計算中…','$1일차: 구간 $2/$3 계산 중…']],
    [/^插入第 (\d+) 项之前$/, ['Insert before stop $1','$1番目の前に挿入','$1번째 장소 앞에 추가']],
    [/^需提前 (\d+) 天预约$/, ['Book $1 days in advance','$1日前までに予約','$1일 전에 예약']],
  ];
  let language = 'zh-CN', initialized = false;

  function supported(value) {
    if (typeof value !== 'string') return null;
    const base = value.toLowerCase().split(/[-_]/)[0];
    return base === 'zh' ? 'zh-CN' : ['en','ja','ko'].includes(base) ? base : null;
  }
  function detect() {
    try {const saved = supported(window.localStorage?.getItem(storageKey));if (saved) return saved;} catch (_) { /* 私密模式可继续使用 */ }
    const preferred = window.navigator?.languages || [window.navigator?.language];
    for (const value of preferred) {const code = supported(value);if (code) return code;}
    return window.navigator ? 'en' : 'zh-CN';
  }
  function translate(value, code=language) {
    const text = String(value ?? '');
    if (code === 'zh-CN' || !dictionaries[code]) return text;
    for (const [pattern, templates] of patterns) {
      const match = pattern.exec(text);
      // $!n preserves a captured user/provider name; $n localizes app text and known POIs.
      if (match) return templates[['en','ja','ko'].indexOf(code)].replace(/\$(!?)(\d+)/g, (_,raw,n)=>raw ? match[Number(n)] || '' : translate(match[Number(n)] || '',code));
    }
    return text.replace(matcher, (match,day) => day !== undefined
      ? code === 'en' ? `Day ${day}` : code === 'ja' ? `${day}日目` : `${day}일차`
      : dictionaries[code][match] ?? match);
  }
  function ignored(node) {
    for (let parent = node.nodeType === 1 ? node : node.parentElement; parent; parent = parent.parentElement) {
      if (['SCRIPT','STYLE','TEXTAREA','CODE'].includes(parent.tagName) || parent.hasAttribute?.('data-i18n-ignore') || parent.isContentEditable) return true;
    }
    return false;
  }
  function update(node, key, value, write) {
    if (!value) return;
    let records = originals.get(node);
    if (!records) {records = new Map(); originals.set(node, records);}
    const previous = records.get(key);
    const source = previous && value === previous.output ? previous.source : value;
    const output = translate(source);
    records.set(key, {source,output});
    if (output !== value) write(output);
  }
  function apply(root) {
    if (!root || ignored(root)) return;
    if (root.nodeType === 3) update(root,'text',root.nodeValue,value=>{root.nodeValue=value;});
    if (root.nodeType === 1) {
      for (const attribute of attributes) update(root,attribute,root.getAttribute?.(attribute),value=>root.setAttribute(attribute,value));
    }
    for (const child of root.childNodes || []) apply(child);
  }
  function setLanguage(code, persist=true) {
    if (!languages.some(item=>item.code === code)) return false;
    language = code;
    if (persist) {try {window.localStorage?.setItem(storageKey,code);} catch (_) { /* 仍即时生效 */ }}
    if (document.documentElement) {document.documentElement.lang=code;apply(document.documentElement);}
    const select = document.getElementById('language-select');
    if (select) select.value=code;
    window.dispatchEvent?.(new Event('inboundroute:languagechange'));
    return true;
  }
  function init() {
    if (initialized) return;
    initialized = true;
    setLanguage(detect(), false);
    const dialog = document.getElementById('settings-dialog');
    const open = document.getElementById('settings-open');
    const close = document.getElementById('settings-close');
    const done = document.getElementById('settings-done');
    const select = document.getElementById('language-select');
    open?.addEventListener('click',()=>dialog.showModal());
    close?.addEventListener('click',()=>dialog.close());
    done?.addEventListener('click',()=>dialog.close());
    select?.addEventListener('change',()=>setLanguage(select.value));
    if (typeof MutationObserver !== 'undefined' && document.documentElement) {
      const observer = new MutationObserver(records=>{
        for (const record of records) {
          if (record.type === 'childList') for (const node of record.addedNodes) apply(node);
          else apply(record.target);
        }
      });
      observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:attributes});
    }
  }
  function localizeHTML(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    apply(template.content);
    return template.innerHTML;
  }
  window.IRLanguage = {languages,translate,setLanguage,init,apply,localizeHTML,get language(){return language;}};
})();
