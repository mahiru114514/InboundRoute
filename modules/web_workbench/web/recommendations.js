"use strict";
/* 推荐日期与原子生成流程；依赖 poi_content。推荐理由只保留在当前页面，不加入持久化行程。 */
const recommendationView = {key:null, selected:new Set(), result:null};

function recommendationContext() {
  const count = state.trip ? state.trip.days.length : Number($('duration-days')?.value);
  const date = state.trip ? state.trip.days[0]?.date : $('arrival-date')?.value;
  return {count, date, key:JSON.stringify([state.trip?.trip_id || null,count,date])};
}

function renderRecommendations() {
  const box = $('recommendation-days');
  if (!box) return;
  const {count,date,key} = recommendationContext();
  if (recommendationView.key !== key) {
    recommendationView.key = key;
    recommendationView.selected = new Set();
    for (let day=2; day<count; day++) recommendationView.selected.add(day);
    recommendationView.result = null;
    if ($('recommendation-progress')) $('recommendation-progress').textContent = '';
  }
  box.replaceChildren();
  if (Number.isInteger(count) && count >= 1 && count <= 15) {
    for (let day=1; day<=count; day++) {
      const label=element('label','recommendation-day');
      const check=element('input');check.type='checkbox';check.value=String(day);
      check.checked=recommendationView.selected.has(day);check.disabled=state.busy;
      const actual=state.trip?.days.find(item=>item.day_index===day)?.date;
      const parsed=new Date(`${date}T00:00:00Z`);parsed.setUTCDate(parsed.getUTCDate()+day-1);
      const dayDate=actual || (Number.isNaN(parsed.getTime()) ? '' : parsed.toISOString().slice(0,10));
      const filled=state.trip?.days.find(item=>item.day_index===day)?.ordered_stops.length;
      label.append(check,element('span','',`第 ${day} 天${dayDate ? ` · ${dayDate}` : ''}${filled ? '（已有安排，保留）' : ''}`));
      check.addEventListener('change',()=>{
        if (check.checked) recommendationView.selected.add(day);else recommendationView.selected.delete(day);
        renderRecommendationStatus();
      });
      box.append(label);
    }
  }
  renderRecommendationStatus();
  renderRecommendationResults();
}

function recommendationUnavailable() {
  const ready=state.services?.ready || {};
  if (!ready.trip_engine) return 'trip_engine 未就绪，请先启动行程模块。';
  if (!ready.recommendation_engine) return 'recommendation_engine 未就绪，请先启动推荐模块；仍可手动保存和编辑行程。';
  return '';
}

function renderRecommendationStatus() {
  const button=$('generate-recommendations'),hint=$('recommendation-hint');
  if (!button || !hint) return;
  const unavailable=recommendationUnavailable();
  button.disabled=Boolean(state.busy || unavailable);
  button.textContent=state.busy ? '正在生成推荐…' : '生成推荐行程';
  hint.textContent=unavailable || (recommendationView.selected.size
    ? '只填充所选空白日，已有安排与锁定点都会保留。可勾选抵达日和返程日。'
    : '请勾选想安排的日期；1～2 天行程默认不勾选抵达日和返程日。');
}

function renderRecommendationResults() {
  const box=$('recommendation-results');if (!box) return;box.replaceChildren();
  const result=recommendationView.result;if (!result) return;
  const hasPlan=result.plan?.days?.some(day=>day.stops?.length);
  box.append(element('p','hint',hasPlan
    ? '推荐已按住宿与出行偏好安排，可继续编辑。交通为规划估算，实际区间交通请在每日行程中计算。'
    : '所选日期没有可新增的推荐安排，请查看原因并调整日期或偏好。'));
  for (const day of result.days || []) {
    const section=element('section','recommendation-result-day');
    section.append(element('h3','',`第 ${day.day_index} 天${day.date ? ` · ${day.date}` : ''}`));
    const list=element('ol','recommendation-stop-list');
    for (const stop of day.stops || []) {
      const item=element('li','recommendation-stop');
      item.append(element('strong','',`${stop.name_zh} · 建议停留 ${stop.planned_dwell_minutes} 分钟`),
        element('p','poi-introduction',poiIntroduction(state.pois?.find(p=>p.poi_id===stop.poi_id))));
      if (stop.reasons?.length) item.append(element('p','recommendation-reason',`推荐理由：${stop.reasons.join('；')}`));
      if (stop.warnings?.length) item.append(element('p','hint',`提示：${stop.warnings.join('；')}`));
      list.append(item);
    }
    section.append(list);box.append(section);
  }
  for (const day of result.skipped_days || []) box.append(element('p','hint',`第 ${day.day_index} 天未新增：${day.reason}`));
  for (const warning of result.warnings || []) box.append(element('p','hint',`提示：${warning}`));
}

function recommendationFormValid() {
  const form=$('setup-form'),budget=$('budget-per-person');
  if (budget) budget.step='any';
  try {return typeof form?.reportValidity !== 'function' || form.reportValidity();}
  finally {if (budget) budget.step='100';}
}

function recommendationSourceChanged(source) {
  if ((state.trip?.trip_id || null) !== source.id || (state.trip?.version ?? null) !== source.version
      || setupSettingsIdentity() !== source.settings
      || JSON.stringify([...recommendationView.selected].sort((a,b)=>a-b)) !== source.days) return true;
  try {return JSON.stringify(readBudget()) !== source.budget;}
  catch (_) {return true;}
}

async function generateRecommendedTrip() {
  if (state.busy) return;
  const unavailable=recommendationUnavailable();
  if (unavailable) {notify(unavailable,true);return;}
  renderRecommendations();
  const dayIndices=[...recommendationView.selected].sort((a,b)=>a-b);
  if (!dayIndices.length) {notify('请先勾选想安排的日期。',true);return;}
  let setup;
  try {
    if (state.trip && (state.setupBaseline !== setupSettingsIdentity()
        || JSON.stringify(readBudget()) !== JSON.stringify(state.trip.budget ?? null))) {
      throw new Error('设定有未保存的更改，请先保存行程，再生成推荐。');
    }
    if (!recommendationFormValid()) return;
    setup=readSetup();
    if (!Number.isInteger(setup.duration_days) || setup.duration_days < 1 || setup.duration_days > 15) throw new Error('行程天数必须是 1~15 的整数');
    if (!Number.isFinite(setup.anchor_arrival.at)) throw new Error('抵达时间无法解析，请检查日期与时刻');
    if (state.trip && dayIndices.every(index=>state.trip.days.find(day=>day.day_index===index)?.ordered_stops.length)) {
      throw new Error('所选日期已有安排，原内容会保留；请改选空白日，或复制行程后调整。');
    }
  } catch (error) {notify(error.message,true);return;}
  const sourceId=state.trip?.trip_id || null;
  const source={id:sourceId,version:state.trip?.version ?? null,settings:setupSettingsIdentity(),
    budget:JSON.stringify(setup.budget),days:JSON.stringify(dayIndices)};
  state.busy=true;
  renderRecommendations();
  $('recommendation-progress').textContent='正在计算所选日期的推荐安排…';
  try {
    const proposal=await api('/api/recommendations:generate',{method:'POST',body:sourceId
      ? {trip_id:sourceId,day_indices:dayIndices} : {setup,day_indices:dayIndices}});
    if (recommendationSourceChanged(source)) throw new Error('行程已切换或设定已更改，推荐未保存；请按当前设定重新生成。');
    if (!proposal.plan?.days?.some(day=>day.stops?.length)) {
      recommendationView.result=proposal;renderRecommendationResults();
      $('recommendation-progress').textContent='没有可新增的推荐安排，请查看原因并调整日期或偏好。';
      return;
    }
    $('recommendation-progress').textContent='推荐已计算，正在保存完整行程…';
    const trip=await api(sourceId ? `/api/trips/${encodeURIComponent(sourceId)}/recommendations:apply` : '/api/trips:recommended',
      {method:'POST',...(sourceId ? {version:proposal.trip_version} : {}),body:sourceId ? {plan:proposal.plan} : {setup,plan:proposal.plan}});
    if (recommendationSourceChanged(source)) {
      await refreshHistorySafely();
      $('recommendation-progress').textContent='推荐已保存到原行程；当前显示的行程和未保存设定已保留。';
      notify('推荐已保存到原行程，当前行程或设定已更改；可从历史列表查看推荐结果。');
      return;
    }
    state.trip=trip;
    if (!sourceId) state.currentDayIndex=1;
    state.setupBaseline=setupSettingsIdentity();
    discardDraft();rememberTrip();resetFlowResults();renderTrip();
    recommendationView.result=proposal;
    renderRecommendationResults();
    $('recommendation-progress').textContent='推荐行程已保存，可在每日行程中继续编辑。';
    await refreshHistorySafely();
    if (typeof afterTripEditSafely === 'function') await afterTripEditSafely('add_stop');
    notify('推荐行程已保存。');
  } catch (error) {
    $('recommendation-progress').textContent=`推荐失败：${error.message}`;
    notify(error.message,true);
  } finally {state.busy=false;renderRecommendations();}
}

function wireRecommendations() {
  $('generate-recommendations')?.addEventListener('click',generateRecommendedTrip);
  $('setup-form')?.addEventListener('input',renderRecommendations);
  $('setup-form')?.addEventListener('change',renderRecommendations);
  renderRecommendations();
}
