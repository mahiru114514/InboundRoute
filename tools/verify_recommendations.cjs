/* 真实后端 + Chromium 隔离验收：临时服务与临时数据，不操作用户行程。 */
'use strict';
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'docs/验收截图');
const fixture = spawn('python', ['-u','-c', [
  'import json, sys',
  'from tests.test_recommendation_integration import RecommendationIntegrationTests',
  "fixture = RecommendationIntegrationTests('test_new_trip_is_created_once_only_after_complete_plan')",
  'try:',
  '    fixture.setUp()',
  "    print(json.dumps({'url':f'http://127.0.0.1:{fixture.web.server_port}'}), flush=True)",
  '    sys.stdin.readline()',
  'finally:',
  '    fixture.doCleanups()',
].join('\n')], {cwd:root, stdio:['pipe','pipe','inherit'], env:{...process.env,PYTHONIOENCODING:'utf-8'}});
const ready = new Promise((resolve,reject)=>{
  let text='';
  fixture.stdout.on('data', chunk=>{
    text+=chunk;
    if (text.includes('\n')) {
      try {resolve(JSON.parse(text.split('\n')[0]).url);} catch(error) {reject(error);}
    }
  });
  fixture.once('error', reject);
  fixture.once('exit', code=>reject(new Error(`隔离服务退出 ${code}`)));
});
(async()=>{
  let browser;
  const checks=[],errors=[];
  function check(label,value) {assert.ok(value,label);checks.push(label);console.log('PASS',label);}
  try {
    const url=await ready;
    const executablePath=process.env.VISUAL_BROWSER_PATH || [
      'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
      'C:/Program Files/Google/Chrome/Application/chrome.exe',chromium.executablePath(),
    ].find(file=>fs.existsSync(file));
    browser=await chromium.launch({headless:true,executablePath});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    let failRate=false,rateHold=null,releaseRate=null;
    await page.route('**/api/currency-rates?*',async route=>{
      const currency=new URL(route.request().url()).searchParams.get('currency');
      if(rateHold) await rateHold;
      await route.fulfill({status:failRate?503:200,contentType:'application/json',body:JSON.stringify(failRate
        ? {ok:false,error:{message:'参考汇率暂时不可用'}}
        : {ok:true,data:{currency,cny_per_unit:currency==='EUR'?8:7,date:'2026-10-07',source:'Frankfurter',cached:false,stale:false}})});
    });
    page.on('pageerror', error=>errors.push(error.message));
    await page.goto(url);await page.evaluate(()=>window.__workbenchBoot);
    check('45个景点均从真实接口取得简介',await page.evaluate(()=>state.pois.length===45 && state.pois.every(p=>typeof p.description_zh==='string' && p.description_zh.trim())));
    const poiList=page.locator('#poi-list');
    const autoToggle=page.locator('#poi-auto-scroll');
    await poiList.scrollIntoViewIfNeeded();
    await poiList.hover();
    await page.waitForFunction(()=>$('poi-list').scrollLeft>20);
    check('无需滚轮景点自动缓慢滚动',await autoToggle.innerText()==='暂停自动滚动');
    const autoLeft=await poiList.evaluate(node=>node.scrollLeft);
    await page.mouse.wheel(0,160);
    await page.waitForFunction(left=>$('poi-list').scrollLeft>left+100,autoLeft);
    check('滚轮接管并按滚轮方向移动',await autoToggle.innerText()==='恢复自动滚动');
    const manualLeft=await poiList.evaluate(node=>node.scrollLeft);
    await page.waitForTimeout(400);
    check('滚轮接管后自动滚动持续退出',await poiList.evaluate((node,left)=>node.scrollLeft===left,manualLeft));
    await page.mouse.wheel(0,-80);
    await page.waitForFunction(left=>$('poi-list').scrollLeft<left-50,manualLeft);
    check('接管后反向滚轮按用户方向浏览',true);
    await autoToggle.click();
    const resumedLeft=await poiList.evaluate(node=>node.scrollLeft);
    await page.waitForFunction(left=>$('poi-list').scrollLeft>left+10,resumedLeft);
    check('明确点击可恢复自动滚动',await autoToggle.innerText()==='暂停自动滚动');
    await poiList.dispatchEvent('pointerdown',{pointerType:'touch'});
    const touchedLeft=await poiList.evaluate(node=>node.scrollLeft);
    await page.waitForTimeout(250);
    check('触屏或鼠标操作同样接管自动滚动',await autoToggle.innerText()==='恢复自动滚动' && await poiList.evaluate((node,left)=>node.scrollLeft===left,touchedLeft));
    await poiList.evaluate(node=>node.scrollLeft=0);
    const firstPoi=page.locator('.poi').first();
    const poiName=await firstPoi.locator('strong').first().innerText();
    const introduction=await page.evaluate(name=>state.pois.find(p=>p.names['zh-Hans']===name).description_zh,poiName);
    check('景点列表显示对应简介',await firstPoi.locator('.poi-introduction').innerText()===introduction);
    await firstPoi.getByRole('button',{name:'详情',exact:true}).click();
    check('详情抽屉显示同一简介',await page.locator('#d-introduction').innerText()===introduction);
    await page.locator('#detail-close').click();
    await poiList.scrollIntoViewIfNeeded();
    await poiList.hover();
    const pageY=await page.evaluate(()=>scrollY);
    await page.mouse.wheel(0,320);
    await page.waitForFunction(()=>$('poi-list').scrollLeft>0);
    check('景点区域滚轮独立横向滚动',await page.evaluate(y=>scrollY===y,pageY));
    const scrolled=await poiList.evaluate(node=>node.scrollLeft);
    await page.mouse.wheel(0,-160);
    await page.waitForFunction(left=>$('poi-list').scrollLeft<left,scrolled);
    check('景点区域支持反向滚轮',await page.evaluate(y=>scrollY===y,pageY));
    await poiList.evaluate(node=>node.scrollLeft=node.scrollWidth);
    // 无行程时这块位于页面底部，先预留纵向空间以实际检验边界释放。
    await page.evaluate(()=>scrollBy(0,-100));
    await poiList.hover();
    const boundaryPageY=await page.evaluate(()=>scrollY);
    await page.mouse.wheel(0,300);
    await page.waitForFunction(y=>scrollY>y,boundaryPageY);
    check('列表末端释放滚轮继续滚动页面',true);
    await poiList.evaluate(node=>node.scrollLeft=0);
    await poiList.focus();
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(()=>$('poi-list').scrollLeft>0);
    check('景点区域保留键盘浏览',true);
    await poiList.evaluate(node=>node.scrollLeft=0);
    await page.locator('#duration-days').fill('5');
    await page.locator('#arrival-date').fill('2026-10-12');
    await page.locator('#arrival-time').fill('09:00');
    await page.locator('input[name="interest"][value="history_culture"]').check();
    check('默认只勾选中间3天',await page.locator('#recommendation-days input:checked').count()===3);
    const hotels=await page.evaluate(()=>anchors('hotels').map(h=>({id:h.id,name:h.name_zh})));
    await page.locator('#hotel-search').fill(hotels[0].name);
    await page.locator('#hotel').selectOption(hotels[0].id);
    check('住宿统一搜索且取消手填和地图点选',await page.locator('#hotel-mode,#hotel-name,#pick-hotel').count()===0);
    await page.locator('#currency-select').selectOption('USD');
    await page.waitForFunction(()=>$('currency-rate').value==='7');
    check('联网参考汇率显示来源与日期',(await page.locator('#currency-hint').innerText()).includes('2026-10-07'));
    await page.evaluate(()=>resetSetup());
    check('新建表单重置保持币种显示与换算一致',await page.evaluate(()=>$('currency-select').value==='USD' && $('currency-rate').value==='7' && readCurrencyBudget('100').amount_cents===70000));
    await page.locator('#duration-days').fill('5');
    await page.locator('#arrival-date').fill('2026-10-12');
    await page.locator('#arrival-time').fill('09:00');
    await page.locator('input[name="interest"][value="history_culture"]').check();
    await page.locator('#hotel-search').fill(hotels[0].name);
    await page.locator('#hotel').selectOption(hotels[0].id);
    await page.locator('#budget-per-person').fill('100');
    await page.locator('#generate-recommendations').click();
    await page.waitForFunction(()=>state.trip && !state.busy);
    const saved=await page.evaluate(()=>structuredClone(state.trip));
    check('搜索选择住宿按名称保存',saved.anchor_hotel.name_zh===hotels[0].name);
    check('100美元预算按人民币整数分保存',saved.budget.amount_cents===70000 && saved.budget.currency==='CNY');
    check('费用评估默认折叠且摘要含外币',!await page.locator('#budget-disclosure').evaluate(n=>n.open) && (await page.locator('#budget-summary').innerText()).includes('USD'));
    check('新建一次保存且首尾为空',saved.version===1 && saved.days[0].ordered_stops.length===0 && saved.days[4].ordered_stops.length===0);
    check('中间日已生成普通可编辑点位',saved.days.slice(1,4).some(day=>day.ordered_stops.length) && saved.days.flatMap(day=>day.ordered_stops).every(stop=>stop.locked===false));
    const explanation=await page.locator('#recommendation-results').innerText();
    check('折叠设定后推荐解释仍可见',explanation.includes('估算') && explanation.includes('建议停留'));
    check('推荐逐景点展示对应简介并保留理由',await page.evaluate(()=>{
      const rows=[...document.querySelectorAll('.recommendation-stop')];
      return rows.length>0 && rows.every(row=>{
        const name=row.querySelector('strong').textContent.split(' · 建议停留 ')[0];
        const poi=state.pois.find(p=>p.names['zh-Hans']===name);
        return poi && row.querySelector('.poi-introduction').textContent===poi.description_zh && row.querySelector('.recommendation-reason')?.textContent;
      });
    }));
    const secondDay=page.locator('.day[data-day-index="2"]');
    await secondDay.locator(':scope > summary').click();
    check('每日起终点与住宿添加默认收起',await secondDay.locator('.day-point-disclosure,.anchor-stop-disclosure').evaluateAll(nodes=>nodes.length===2 && nodes.every(n=>!n.open)));
    const dayPoi=await page.evaluate(()=>state.pois.find(p=>p.poi_id===state.trip.days[1].ordered_stops[0].poi_id));
    check('每日行程按POI主数据显示简介',await secondDay.locator('.stop .poi-introduction').first().innerText()===dayPoi.description_zh);
    fs.mkdirSync(output,{recursive:true});
    await page.locator('#setup-disclosure').evaluate(node=>node.open=true);
    await page.screenshot({path:path.join(output,'recommendations-desktop.png'),fullPage:true});
    await secondDay.screenshot({path:path.join(output,'poi-introductions-day-desktop.png')});
    for (const width of [768,390,320]) {
      await page.setViewportSize({width,height:844});
      check(`${width}px页面无横向溢出`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      check(`${width}px景点溢出限制在自身容器`,await poiList.evaluate(node=>node.scrollWidth>node.clientWidth && node.getBoundingClientRect().right<=innerWidth));
    }
    await page.screenshot({path:path.join(output,'recommendations-mobile.png'),fullPage:true});
    await secondDay.screenshot({path:path.join(output,'poi-introductions-day-mobile.png')});
    await page.reload();await page.evaluate(()=>window.__workbenchBoot);
    check('刷新恢复搜索住宿、外币偏好与完整行程',await page.evaluate(name=>state.trip?.trip_id && state.trip.anchor_hotel.name_zh===name && $('hotel').value && $('currency-select').value==='USD' && state.trip.budget.amount_cents===70000,hotels[0].name));
    await page.waitForFunction(()=>$('currency-rate').value==='7');
    await page.locator('#setup-disclosure').evaluate(node=>node.open=true);
    const first=page.locator('#recommendation-days input[value="1"]');
    await first.check();
    for(const day of [2,3,4]) await page.locator(`#recommendation-days input[value="${day}"]`).uncheck();
    await page.locator('#generate-recommendations').click();
    await page.waitForFunction(()=>state.trip.version===2 && !state.busy);
    const updated=await page.evaluate(()=>structuredClone(state.trip));
    check('已有行程补首日且中间安排保留',updated.days[0].ordered_stops.length>0 && JSON.stringify(updated.days.slice(1,4))===JSON.stringify(saved.days.slice(1,4)));
    const removed=updated.days[1].ordered_stops[0];
    const retained=updated.days[1].ordered_stops.slice(1).map(stop=>stop.stop_id);
    const editableDay=page.locator('.day[data-day-index="2"]');
    await editableDay.locator(':scope > summary').click();
    await editableDay.locator('.stop').first().getByRole('button',{name:'移除',exact:true}).click();
    await page.waitForFunction(()=>state.trip.version===3 && !state.busy);
    check('阅读简介后可移除景点且保留其他点',await page.evaluate(({id,retained})=>{
      const stops=state.trip.days[1].ordered_stops;
      return !stops.some(stop=>stop.stop_id===id) && JSON.stringify(stops.map(stop=>stop.stop_id))===JSON.stringify(retained);
    },{id:removed.stop_id,retained}));
    check('移除后的日卡同步更新',await editableDay.locator('.stop').count()===retained.length);
    await page.reload();await page.evaluate(()=>window.__workbenchBoot);
    check('重载旧行程后简介仍显示且移除结果保留',await page.evaluate(id=>{
      const stops=state.trip.days[1].ordered_stops;
      const rows=[...document.querySelectorAll('.day[data-day-index="2"] .stop .poi-introduction')];
      return !stops.some(stop=>stop.stop_id===id) && rows.length===stops.length && rows.every((row,i)=>row.textContent===state.pois.find(p=>p.poi_id===stops[i].poi_id).description_zh);
    },removed.stop_id));
    await page.setViewportSize({width:1440,height:1000});
    await editableDay.locator(':scope > summary').click();
    const nights=await page.evaluate(()=>JSON.stringify(state.trip.budget_assessment.defaults.lodging_nights));
    await editableDay.locator('.anchor-stop-disclosure > summary').click();
    await editableDay.locator('.anchor-stop-search').fill(hotels[1].name);
    await editableDay.locator('.anchor-stop-picker select.day-point-select').selectOption('hotel:'+hotels[1].id);
    await editableDay.locator('.hotel-stay-kind').selectOption('rest');
    await editableDay.locator('.anchor-position').selectOption('1');
    await editableDay.getByRole('button',{name:'添加到行程',exact:true}).click();
    await page.waitForFunction(()=>state.trip.version===4 && !state.busy);
    check('途中休息可插入指定位置并保留其他景点',await page.evaluate(ids=>state.trip.days[1].ordered_stops[0].hotel_stay_kind==='rest' && state.trip.days[1].ordered_stops[0].planned_dwell_minutes===60 && JSON.stringify(state.trip.days[1].ordered_stops.slice(1).map(s=>s.stop_id))===JSON.stringify(ids),retained));
    check('途中休息不改变后续住宿及房费晚数',await page.evaluate(({nights,name})=>JSON.stringify(state.trip.budget_assessment.defaults.lodging_nights)===nights && state.trip.default_day_points[3].start.name_zh===name,{nights,name:hotels[0].name}));
    await editableDay.locator('.stop').first().getByRole('button',{name:'移除',exact:true}).click();
    await page.waitForFunction(()=>state.trip.version===5 && !state.busy);
    check('住宿点可像景点一样移除',await page.evaluate(ids=>JSON.stringify(state.trip.days[1].ordered_stops.map(s=>s.stop_id))===JSON.stringify(ids),retained));
    await page.locator('#setup-disclosure').evaluate(node=>node.open=true);
    await page.locator('#currency-select').selectOption('CNY');
    rateHold=new Promise(resolve=>{releaseRate=resolve;});
    await page.locator('#currency-select').selectOption('USD');
    await page.evaluate(()=>loadSavedTrip(state.trip.trip_id));
    rateHold=null;releaseRate();
    await page.waitForFunction(()=>$('currency-rate').value==='7');
    check('汇率请求期间切换行程保留当前预算',await page.evaluate(()=>$('budget-per-person').value==='100.00' && readBudget().amount_cents===70000 && state.trip.budget.amount_cents===70000));
    await page.locator('#budget-summary').click();
    await page.locator('#budget-assessment summary').filter({hasText:'填写 / 核对费用'}).click();
    const extras=page.locator('input[data-cost-field="extras_cents"]');
    await extras.fill('88.88');
    await page.locator('#setup-disclosure').evaluate(node=>node.open=true);
    await page.locator('#currency-rate').fill('7.2');
    check('手改汇率保留费用编辑与人民币预算',await extras.inputValue()==='88.88' && await page.locator('#budget-disclosure').evaluate(n=>n.open) && await page.evaluate(()=>state.trip.budget.amount_cents===70000 && readBudget().amount_cents===70000));
    failRate=true;
    await page.locator('#currency-refresh').click();
    await page.waitForFunction(()=>$('currency-hint').textContent.includes('不可用') || $('currency-hint').textContent.includes('失败'));
    check('参考汇率失败保留手动汇率和未保存输入',await page.locator('#currency-rate').inputValue()==='7.2' && await extras.inputValue()==='88.88');
    await page.waitForFunction(()=>$('toast').hidden);
    await page.screenshot({path:path.join(output,'tester-feedback-desktop.png'),fullPage:true});
    for(const width of [768,390,320]) {
      await page.setViewportSize({width,height:844});
      check(`${width}px展开费用编辑无横向溢出`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    }
    await page.screenshot({path:path.join(output,'tester-feedback-mobile.png'),fullPage:true});
    await page.locator('#budget-summary').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'tester-feedback-mobile-budget.png')});
    await page.locator('#currency-select').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'tester-feedback-mobile-settings.png')});
    await page.locator('#trip-history').selectOption('');
    await page.waitForFunction(()=>!state.trip);
    check('历史切换新建行程保持币种与预算状态一致',await page.evaluate(()=>$('currency-select').value==='USD' && $('currency-rate').value==='7.2' && $('budget-per-person').value==='' && readCurrencyBudget('100').amount_cents===72000));
    check('浏览器无脚本异常',errors.length===0);
    const reduced=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    await reduced.goto(url);await reduced.evaluate(()=>window.__workbenchBoot);
    await reduced.locator('#poi-list').scrollIntoViewIfNeeded();
    await reduced.waitForTimeout(250);
    check('减少动态效果偏好关闭默认自动滚动',await reduced.locator('#poi-list').evaluate(node=>node.scrollLeft===0)
      && await reduced.locator('#poi-auto-scroll').innerText()==='恢复自动滚动');
    await reduced.close();
    fs.writeFileSync(path.join(output,'recommendations-verification.json'),JSON.stringify({checks,errors,isolated:true},null,2));
    fs.writeFileSync(path.join(output,'poi-introductions-verification.json'),JSON.stringify({checks,errors,isolated:true},null,2));
    fs.writeFileSync(path.join(output,'poi-scroll-verification.json'),JSON.stringify({checks,errors,isolated:true},null,2));
    fs.writeFileSync(path.join(output,'poi-auto-scroll-verification.json'),JSON.stringify({checks,errors,isolated:true},null,2));
    fs.writeFileSync(path.join(output,'tester-feedback-verification.json'),JSON.stringify({checks,errors,isolated:true},null,2));
    console.log(`${checks.length} browser checks passed`);
  } finally {
    if(browser) await browser.close();
    fixture.stdin.end('\n');
    await new Promise(resolve=>{if(fixture.exitCode!==null) resolve();else fixture.once('exit',resolve);});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});

