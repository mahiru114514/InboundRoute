"use strict";
// Real catalog and temporary services; browser changes never reach user trip data.
const {chromium}=require(process.argv[2] || 'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const root=path.resolve(__dirname,'..');
const script=`import sys, json, tempfile, threading
from pathlib import Path
from modules.web_workbench.engine import build_server
from modules.web_workbench.proxy import ServiceRegistry
from modules.trip_engine.engine import TripService, build_server as build_trip
from contracts.runtime.registry import CONTRACT_VERSION
with tempfile.TemporaryDirectory() as folder:
    workspace=Path(folder)
    registry=workspace/'data'/'_registry'
    registry.mkdir(parents=True)
    trip=build_trip(TripService(workspace/'data'/'trip_engine'), 'isolated-trip-token', 0)
    threading.Thread(target=trip.serve_forever,daemon=True).start()
    (registry/'trip_engine.json').write_text(json.dumps({'module_id':'trip_engine','port':trip.server_port,'base_url':f'http://127.0.0.1:{trip.server_port}','token':'isolated-trip-token','pid':1,'contract_version':CONTRACT_VERSION,'started_at':0,'depends_on':[],'endpoints':['/health']}),encoding='utf-8')
    server=build_server(ServiceRegistry(workspace), 'isolated-content-token', 0, maps={'provider':'none','ready':False})
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print(server.server_port,flush=True)
    sys.stdin.read()
    server.shutdown(); server.server_close()
    trip.shutdown(); trip.server_close()
`;
(async()=>{
  const child=spawn(process.env.CONTENT_TEST_PYTHON || 'python',['-u','-c',script],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
  let browser;
  try {
    const port=await new Promise((resolve,reject)=>{
      child.once('error',reject);child.once('exit',code=>reject(Error(`server exited ${code}`)));
      child.stderr.on('data',data=>process.stderr.write(data));
      let output='';child.stdout.on('data',data=>{output+=data;if(output.includes('\n'))resolve(Number(output.trim()));});
    });
    browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
    const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
    await context.addInitScript(()=>localStorage.setItem('inboundroute.onboarding.seen','1'));
    const page=await context.newPage(),errors=[];
    const shots=path.join(root,'docs','language-content-preview');fs.mkdirSync(shots,{recursive:true});
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`http://127.0.0.1:${port}/`);
    await page.evaluate(()=>window.__workbenchBoot);
    assert.equal(await page.locator('#poi-list .poi-introduction').count(),45);
    const original=await page.locator('#poi-list .poi-introduction').allTextContents();
    // Switch through real settings to cover observer updates, then update an open detail.
    await page.locator('#settings-open').click();
    await page.locator('#language-select').selectOption('en');
    await page.locator('#settings-done').click();
    await page.waitForFunction(()=>[...document.querySelectorAll('#poi-list .poi-introduction')].every(el=>!/[\u4e00-\u9fff]/.test(el.textContent)));
    async function auditEnglish(){const residual=await page.evaluate(()=>{
      const names=[...state.pois.map(p=>p.names['zh-Hans']),...(state.anchors.hubs||[]).map(p=>p.name_zh),...(state.anchors.hotels||[]).map(p=>p.name_zh),'我的酒店','我的机场','我的车站'].filter(Boolean).sort((a,b)=>b.length-a.length);
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),issues=[];
      let node;while(node=walker.nextNode()){
        if(node.parentElement.closest('script,style,textarea,code,[data-i18n-ignore],.pin'))continue;
        let text=node.textContent.trim();for(const name of names)text=text.replaceAll(name,'<place>');
        if(/[\u4e00-\u9fff]/.test(text))issues.push({element:node.parentElement.id||node.parentElement.className,text});
      }
      return issues;
    });
    fs.writeFileSync(path.join(shots,'residual-english.json'),JSON.stringify(residual,null,2));
    assert.deepEqual(residual,[],'English interface must not contain untranslated built-in labels or source metadata');}

    await auditEnglish();
    // Check all 45 detail drawers, including tags, closure notes and drop-off text.
    for(const id of await page.evaluate(()=>state.pois.map(p=>p.poi_id))) {
      await page.evaluate(id=>openDetail(state.pois.find(p=>p.poi_id===id)),id);
      await page.waitForFunction(()=>!/[\u4e00-\u9fff]/.test(document.getElementById('d-introduction').textContent));
      const rows=await page.locator('#d-rows').innerText();
      assert.ok(!/[\u4e00-\u9fff]/.test(rows),`${id}: English detail metadata incomplete: ${rows}`);
      await page.locator('#detail-close').click();
    }
    await page.evaluate(()=>openDetail(state.pois.find(p=>p.poi_id==='sh_poi_00122')));
    for(const code of ['en','ja','ko','zh-CN','en']) {
      await page.evaluate(code=>window.IRLanguage.setLanguage(code),code);
      await page.waitForFunction(code=>document.getElementById('d-introduction').textContent===window.IRLanguage.translate(state.pois.find(p=>p.poi_id==='sh_poi_00122').description_zh,code),code).catch(async error=>{console.error(await page.evaluate(code=>({code,actual:document.getElementById('d-introduction').textContent,expected:window.IRLanguage.translate(state.pois.find(p=>p.poi_id==='sh_poi_00122').description_zh,code)}),code));throw error;});
    }
    fs.writeFileSync(path.join(shots,'poi-detail-en-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
    await page.locator('#detail-close').click();
    // Render representative backend suggestions without making business mutations.
    await page.evaluate(()=>{
      window.__languageCheckTrip={trip_id:'view-only',version:1,days:[],budget_assessment:{total:{min_cents:10000,max_cents:12000},complete:true,status:'over_budget',budget_cents:9000,categories:{},defaults:{dates:[],lodging_nights:[]},suggestions:[
        {kind:'ticket',title:'评估减少 豫园 的付费游览',body:'若取消这次付费游览，每人可减少这次计入的门票估算；请在当天行程自行调整。',savings_min_cents:4000,savings_max_cents:4000},
        {kind:'transit',title:'Day 1 第 2 段交通（返程 / 终点）可考虑公共交通',body:'到当天交通卡选择公共交通；切换后重新计算行程时间。费用来自当前可用方案。',extra_minutes:12.5,savings_min_cents:2000,savings_max_cents:3000},
        {kind:'budget',title:'需要压缩支出或调整每人预算',body:'若保留当前安排，可参考完整费用估算区间调整每人预算。',required_reduction_cents:3000},
      ]}};
      state.trip=window.__languageCheckTrip;
      document.getElementById('trip-panel').hidden=false;
      renderBudgetAssessment();
      document.getElementById('budget-disclosure').open=true;
      document.getElementById('budget-disclosure').scrollIntoView({behavior:'instant',block:'start'});
    });
    await page.waitForFunction(()=>!/[\u4e00-\u9fff]/.test([...document.querySelectorAll('#budget-assessment>.hint')].slice(-3).map(el=>el.textContent).join('')));
    const english=await page.locator('#budget-assessment').innerText();
    assert.match(english,/Yu Garden/);
    assert.match(english,/12\.5/);
    fs.writeFileSync(path.join(shots,'suggestions-en-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
    await page.evaluate(()=>{
      state.trip.days=[{day_index:1,date:'2026-10-12',ordered_stops:[{poi_id:'sh_poi_00122',arrival_at:1791786000,transit_from_previous:{duration_seconds:1200}}]}];
      const list=document.getElementById('rule-notices');list.replaceChildren();
      document.getElementById('rules-panel').hidden=false;
      window.__languageNoticeResult={notices:[
        {message_key:'rule.lightup.too_early',message_args:{day_index:1,poi_id:'sh_poi_00122',arrival_local:'16:30',T_light:'18:00',light_start:'18:00',light_close:'22:00'},severity:'soft'},
        {message_key:'rule.spread.long_transit',message_args:{day_index:1,from_name_zh:'豫园',to_name_zh:'金茂大厦',duration_minutes:65,distance_km:18},severity:'soft'},
        {message_key:'rule.homogeneous.banner',message_args:{day_index:1,count:3,category_zh:'自然生态'},severity:'soft'},
      ]};renderTripReminders(list,window.__languageNoticeResult,true);
      document.getElementById('rules-panel').scrollIntoView({behavior:'instant',block:'start'});
    });
    await page.waitForFunction(()=>!/[\u4e00-\u9fff]/.test(document.getElementById('rule-notices').innerText));
    assert.match(await page.locator('.reminder-suggest').innerText(),/Suggestions/);
    fs.writeFileSync(path.join(shots,'reminder-suggestions-en-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
    // Keep temporary fixture service state stable during multilingual checks.
    const services=await page.evaluate(()=>({services:state.services.services.map(item=>({...item,ready:true})),ready:Object.fromEntries(state.services.services.map(item=>[item.module_id,true]))}));
    await page.route('**/api/services',route=>route.fulfill({json:{ok:true,data:services}}));
    await page.evaluate(services=>{state.services=services;flow.evaluations=window.__languageNoticeResult;},services);
    // Populate every dynamic workbench surface using view-only data.
    await page.evaluate(()=>{
      const poi=state.pois.find(p=>p.poi_id==='sh_poi_00122');
      const point={lat:31.23,lng:121.47,crs:'WGS84'};
      const hotel={type:'hotel',name_zh:'我的酒店',name_en:'My hotel',coordinate:point};
      Object.assign(state.trip,{user_profile:{party_composition:'solo',pacing:'balanced',interests:['history']},budget:{amount_cents:9000,currency:'CNY'},anchor_arrival:{location_name:'我的机场',at:1791766800,activity_start_at:1791766800,coordinate:point},anchor_hotel:hotel,anchor_departure:{location_name:'我的车站',coordinate:point}});
      state.trip.resolved_day_points={1:{start:hotel,end:hotel}};state.trip.default_day_points=state.trip.resolved_day_points;
      Object.assign(state.trip.days[0],{daily_start_local:'09:00',day_status:'partial',poi_cap:3,ordered_stops:[{poi_id:poi.poi_id,stop_id:'view-only-stop',stop_type:'poi',stop_order:1,locked:true,planned_dwell_minutes:90,arrival_at:1791786000,departure_at:1791791400,rule_notices:[],transit_from_previous:{mode:'walk',data_source:'amap',duration_seconds:1200,from:{name_zh:'我的酒店'},to:{name_zh:poi.names['zh-Hans'],poi_id:poi.poi_id},polyline:'121.4,31.2;121.41,31.21',segments:[{kind:'walk',duration_seconds:300,distance_meters:400}],variants:[{mode:'walk',duration_seconds:1200,distance_meters:1000,cost:{min:0,max:0}}]}}]});
      renderTrip();document.querySelector('#days details.day').open=true;
      recommendationView.result={plan:{days:[{stops:[{poi_id:poi.poi_id}]}]},days:[{day_index:1,date:'2026-10-12',stops:[{poi_id:poi.poi_id,name_zh:poi.names['zh-Hans'],planned_dwell_minutes:90,reasons:['匹配所选兴趣','按每日起终点及区域距离安排顺序','已预留停留、交通估算及休息时间'],warnings:[]}]}],skipped_days:[],warnings:[]};renderRecommendationResults();
      flow.offline={trip_id:'view-only',trip_version:1,generated_at:Math.floor(Date.now()/1000),ttl_hours:24,payload:{days:[{day_index:1,date:'2026-10-12',daily_start_local:'09:00',start_anchor:hotel,end_anchor:hotel,end_transfer_required:false,stops:[{name_zh:poi.names['zh-Hans'],name_en:poi.names.en,stop_type:'poi',planned_dwell_minutes:90,arrival_at:1791786000,departure_at:1791791400,mode:'walk',duration_seconds:1200,ask_cards:[{template_key:'poi_arrival',args:{poi_name_zh:poi.names['zh-Hans'],poi_name_en:poi.names.en}}]}]}]}};
      renderOffline(flow.offline);
      document.getElementById('poi-search').value='我的搜索草稿';
      window.__languageTripBefore=JSON.stringify(state.trip);
    });
    const originalBySurface=await page.evaluate(()=>Object.fromEntries(['#poi-list .poi-introduction','#days .poi-introduction','#recommendation-results .poi-introduction'].map(selector=>[selector,[...document.querySelectorAll(selector)].map(el=>window.IRPoiLanguageCatalog.find(row=>row.includes(el.textContent))?.[0])])));
    for(const code of ['en','ja','ko','zh-CN','en']) {
      await page.evaluate(code=>{window.IRLanguage.setLanguage(code);const list=document.getElementById('rule-notices');list.replaceChildren();renderTripReminders(list,window.__languageNoticeResult,true);},code);
      await page.waitForFunction(code=>document.documentElement.lang===code && document.getElementById('offline-preview').firstElementChild.lang===code,code);
      for(const [selector,sources] of Object.entries(originalBySurface)) {
        assert.equal(sources.filter(Boolean).length,sources.length,`${selector}: every introduction must map to a complete catalog row`);
        const expected=await page.evaluate(({sources,code})=>sources.map(source=>window.IRLanguage.translate(source,code)),{sources,code});
        assert.deepEqual(await page.locator(selector).allTextContents(),expected,`${selector}/${code}`);
      }
      if(code==='en')await auditEnglish();
      const budget=await page.locator('#budget-assessment').innerText();
      const notices=await page.locator('#rule-notices').innerText();
      assert.equal(await page.locator('.reminder-suggest article').count(),3,`${code}: all suggestion examples must remain rendered`);
      if(code==='en'||code==='ko') {
        assert.ok(!/[\u4e00-\u9fff]/.test(budget),`Budget contains Chinese in ${code}: ${budget}`);
        assert.ok(!/[\u4e00-\u9fff]/.test(notices),`Reminder contains Chinese in ${code}: ${notices}`);
      }
      assert.equal(await page.locator('#poi-search').inputValue(),'我的搜索草稿');
      assert.equal(await page.locator('#days details.day').evaluate(el=>el.open),true);
      assert.equal(await page.evaluate(()=>JSON.stringify(state.trip)),await page.evaluate(()=>window.__languageTripBefore));
      const exported=await page.evaluate(code=>offlineDocument(flow.offline,code),code);
      assert.match(exported,new RegExp(`lang="${code}"`));
      assert.ok(exported.includes('金茂大厦'),'Offline directions retain the original Chinese place name');
      await page.evaluate(()=>document.getElementById('rules-panel').scrollIntoView({behavior:'instant',block:'start'}));
      if(code!=='zh-CN')fs.writeFileSync(path.join(shots,`workbench-${code}-2026-10-08.png`),await page.screenshot({animations:'disabled'}));
    }
    await page.evaluate(()=>window.IRLanguage.setLanguage('zh-CN'));
    await page.waitForFunction(()=>[...document.querySelectorAll('#budget-assessment>.hint')].some(el=>el.textContent.includes('评估减少 豫园')));
    assert.deepEqual(await page.locator('#poi-list .poi-introduction').allTextContents(),original);
    await page.evaluate(()=>{window.IRLanguage.setLanguage('en');state.trip=null;});
    await page.reload();await page.evaluate(()=>window.__workbenchBoot);
    assert.equal(await page.locator('html').getAttribute('lang'),'en');
    assert.equal(await page.locator('#poi-list .poi-introduction').count(),45);
    await page.waitForFunction(()=>[...document.querySelectorAll('#poi-list .poi-introduction')].every(el=>!/[\u4e00-\u9fff]/.test(el.textContent)));
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>document.getElementById('poi-panel').scrollIntoView({behavior:'instant',block:'start'}));
    await page.locator('#poi-panel h2').waitFor({state:'visible'});
    assert.ok(await page.locator('#poi-panel').evaluate(el=>el.getBoundingClientRect().top>=0&&el.getBoundingClientRect().top<300),'Mobile content must be in the screenshot viewport');
    await page.locator('#poi-list .poi').first().evaluate(el=>el.scrollIntoView({behavior:'instant',block:'start'}));
    assert.ok(await page.locator('#poi-list .poi-introduction').first().evaluate(el=>el.getBoundingClientRect().top<650),'Mobile introduction must be readable in the viewport');
    fs.writeFileSync(path.join(shots,'poi-list-en-mobile-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
    assert.deepEqual(errors,[]);
    console.log('Content language browser: 45 real introductions on list/day/recommendation/detail, all four languages, budget/reminder suggestions, offline exports, input/data/disclosure preservation, English UI audit, refresh and mobile passed.');
  } finally {
    if(browser)await browser.close();
    const closed=once(child,'exit');child.stdin.end();await closed;
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
