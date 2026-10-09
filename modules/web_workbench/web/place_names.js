"use strict";
/* 共用名称显示；仅更新绑定的文字节点，保持表单、焦点、展开状态。 */
const placeNames={entries:new Map(),nodes:new Map(),editorTexts:new Map(),editorInputs:new Map(),translationVersion:null,signature:null,request:0};
function placeLanguage() {
  const lang=typeof window!=='undefined' ? window.IRLanguage : null;
  return lang?.language || lang?.getLanguage?.() || 'zh-CN';
}
function placePoint(point) {
  if(typeof point==='string') point={name_zh:point};
  point=point || {};
  const poi=typeof state!=='undefined' ? (state.pois || []).find(p=>p.poi_id===point.poi_id || p.names?.['zh-Hans']===point.name_zh) : null;
  const original=point.name_zh || poi?.names?.['zh-Hans'] || '';
  const anchors=typeof state!=='undefined' ? [...(state.anchors?.hotels || []),...(state.anchors?.hubs || [])] : [];
  const known=anchors.find(p=>p.name_zh===original);
  let english=point.name_en;
  if((point.name_en_for_zh || point.source_name_zh) && (point.name_en_for_zh || point.source_name_zh)!==original) english=null;
  if(!english || /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u{20000}-\u{2fa1f}\u{30000}-\u{323af}]/u.test(english)) english=poi?.names?.['zh-Hans']===original ? poi.names.en : known?.name_en;
  const result={name_zh:original,name_en:english || null,type:point.type || point.stop_type || (point.station_id ? 'station' : point.poi_id ? 'poi' : 'place')};
  for(const key of ['city','place_id','station_id','poi_id','id','coordinate','name_en_for_zh']) if(point[key]!=null) result[key]=point[key];
  return result;
}
function placeClientKey(point) {
  const p=placePoint(point),c=p.coordinate || {};
  return JSON.stringify([p.city || 'Shanghai',p.type,p.place_id || p.station_id || p.poi_id || p.id || [c.lat ?? null,c.lng ?? null],p.name_zh.trim(),'en']);
}
function placeDisplayName(point,locale=placeLanguage()) {
  const p=placePoint(point),entry=placeNames.entries.get(placeClientKey(p));
  let zh=p.name_zh,en=entry?.name_en || p.name_en;
  if(!zh) return '';
  if(locale==='zh-CN') return zh;
  let display=en && zh.endsWith(' / '+en) ? zh : en && en!==zh ? zh+' / '+en : zh;
  if(entry?.status==='candidate') display+=' ['+({en:'Unconfirmed',ja:'未確認',ko:'미확인'}[locale] || 'Unconfirmed')+']';
  if(entry?.status==='missing') display+=' ['+({en:'No English name',ja:'英語表記なし',ko:'영문 이름 없음'}[locale] || 'No English name')+']';
  return display;
}
function placeNameNode(node,point) {
  node.setAttribute('data-i18n-ignore','');
  placeNames.nodes.set(node,point);
  node.textContent=placeDisplayName(point);
  return node;
}
function bindDaySequence(node,points) {placeNames.nodes.set(node,points);}
function refreshPlaceNameNodes() {
  for(const [node,zh] of placeNames.editorTexts) {
    if(node.isConnected===false) {placeNames.editorTexts.delete(node);continue;}
    node.textContent=placeEditorLabel(zh);
  }
  for(const [node,name] of placeNames.editorInputs) {
    if(node.isConnected===false) {placeNames.editorInputs.delete(node);continue;}
    node.setAttribute('aria-label',placeEditorLabel('英文地名')+' · '+name);
  }
  for(const [node,point] of placeNames.nodes) {
    if(node.isConnected===false) {placeNames.nodes.delete(node);continue;}
    node.textContent=Array.isArray(point) ? point.map(p=>placeDisplayName(p)).filter(Boolean).join(' → ') : placeDisplayName(point);
  }
}
async function refreshPlaceNames(force=false) {
  if(typeof api!=='function' || typeof engineReady!=='function' || !engineReady('offline_kit')) return;
  const points=new Map();
  const add=point=>{const p=placePoint(point);if(p.name_zh) points.set(placeClientKey(p),p);};
  const walk=node=>{
    if(Array.isArray(node)) node.forEach(walk);
    else if(node && typeof node==='object') {
      if(node.name_zh) add(node);
      if(node.station_name_zh) add({type:'station',station_id:node.station_id,name_zh:node.station_name_zh,name_en:node.station_name_en});
      Object.values(node).forEach(walk);
    }
  };
  walk(state.trip);
  for(const day of state.trip?.days || []) for(const stop of day.ordered_stops || []) add(stop);
  const list=[...points.values()].slice(0,1000);
  const signature=JSON.stringify([state.trip?.trip_id,state.trip?.version,list]);
  if(!force && signature===placeNames.signature) return;
  placeNames.signature=signature;
  const request=++placeNames.request;
  try {
    const data=await api('/api/place-names',{method:'POST',body:{points:list}});
    if(request!==placeNames.request) return;
    for(const entry of data.entries || []) placeNames.entries.set(placeClientKey(entry.point),entry);
    placeNames.translationVersion=data.translation_version;
    refreshPlaceNameNodes();
  } catch(_) {if(request===placeNames.request) placeNames.signature=null;}
}
function placeEditorLabel(zh) {return typeof window!=='undefined' && window.IRLanguage ? window.IRLanguage.translate(zh) : zh;}
function placeEditorText(node,zh) {
  placeNames.editorTexts.set(node,zh);
  node.textContent=placeEditorLabel(zh);
  return node;
}
function renderPlaceTranslationEditor(pkg) {
  const box=$('place-translation-editor');if(!box) return;
  box.replaceChildren();
  const items=pkg.payload?.translation_report?.items || [];
  if(!items.length) return;
  const disclosure=element('details','place-translation-editor');
  disclosure.append(placeEditorText(element('summary'),'核对地名英文'));
  disclosure.append(placeEditorText(element('p','hint'),'拼音候选尚未确认。可填写正确英文，保存后会重新生成离线卡片。'));
  for(const item of items) {
    const row=element('div','place-translation-row');
    const label=element('label','',item.name_zh);label.setAttribute('data-i18n-ignore','');
    const input=element('input');input.type='text';input.value=item.name_en || '';input.maxLength=200;
    input.setAttribute('aria-label',placeEditorLabel('英文地名')+' · '+item.name_zh);
    placeNames.editorInputs.set(input,item.name_zh);
    label.append(input);
    const save=placeEditorText(element('button','secondary'),'确认英文并更新卡片');save.type='button';
    save.addEventListener('click',()=>flowAction(async()=>{
      const data=await api('/api/place-names:confirm',{method:'POST',body:{point:item.point,name_en:input.value}});
      placeNames.translationVersion=data.translation_version;
      placeNames.entries.clear();placeNames.signature=null;
      flow.offline=null;
      await refreshPlaceNames(true);
      await generateOffline();
    }));
    row.append(label,save);disclosure.append(row);
  }
  box.append(disclosure);
}
if(typeof window!=='undefined') window.addEventListener?.('inboundroute:languagechange',refreshPlaceNameNodes);
