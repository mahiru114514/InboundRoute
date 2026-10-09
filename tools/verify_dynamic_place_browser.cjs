"use strict";
const {chromium}=require(process.argv[2]);
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
(async()=>{
  const child=spawn('python',['-B','-X','utf8','-u','tools/verify_dynamic_place_server.py'],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
  let browser;
  try {
    const port=await new Promise((resolve,reject)=>{
      child.once('error',reject);child.once('exit',code=>reject(Error('Fixture exited '+code)));
      child.stderr.on('data',data=>process.stderr.write(data));
      let text='';child.stdout.on('data',data=>{text+=data;if(text.includes('\n'))resolve(Number(text.trim()));});
    });
    browser=await chromium.launch({headless:true,executablePath:process.argv[3]});
    const context=await browser.newContext({locale:'en',viewport:{width:1440,height:1000}});
    await context.addInitScript(()=>{localStorage.setItem('inboundroute.language','en');localStorage.setItem('inboundroute.onboarding.seen','1');});
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${port}/`);await page.evaluate(()=>window.__workbenchBoot);
    await page.waitForFunction(()=>document.querySelector('.day-sequence')?.textContent.includes('Century Park'));
    assert.equal(await page.locator('.day-sequence').count(),3);
    assert.ok((await page.locator('.day-sequence').first().innerText()).includes('Shanghai Marriott Marquis'));
    await page.locator('#days details.day').first().evaluate(el=>el.open=true);
    await page.locator('#poi-search').fill('unsaved search');
    const before=await page.evaluate(()=>JSON.stringify(state.trip));
    for(const code of ['zh-CN','ja','ko','en']) {
      await page.evaluate(code=>window.IRLanguage.setLanguage(code),code);
      assert.equal(await page.locator('#poi-search').inputValue(),'unsaved search');
      assert.equal(await page.locator('#days details.day').first().evaluate(el=>el.open),true);
      assert.equal(await page.evaluate(()=>JSON.stringify(state.trip)),before);
      assert.equal((await page.locator('.day-sequence').first().innerText()).includes('Century Park'),code!=='zh-CN');
    }
    await page.locator('#days details.day').first().evaluate(el=>el.open=false);
    const output=path.join(root,'docs/验收截图');fs.mkdirSync(output,{recursive:true});
    await page.locator('#days').screenshot({path:path.join(output,'dynamic-day-names-en-2026-10-09.png')});
    await page.locator('#generate-offline').click();
    await page.waitForFunction(()=>!!flow.offline);
    await page.locator('#offline-preview .offline-stop').first().waitFor({state:'visible'});
    const preview=await page.locator('#offline-preview').innerText();
    for(const name of ['Changyi Road','Yingchun Road','Line 18 (Kangwen Road — Hangtou)','Unconfirmed place names']) assert.ok(preview.includes(name),name);
    const editor=page.locator('#place-translation-editor details');await editor.locator('summary').click();
    // All appearances of the manual hotel must share one identity and one editor row.
    assert.equal(await editor.locator('input').count(),1);
    await editor.locator('input').fill('Test Inn');
    await editor.locator('input').focus();
    for(const code of ['zh-CN','ja','ko','en']) {
      await page.evaluate(code=>window.IRLanguage.setLanguage(code),code);
      assert.equal(await editor.locator('input').inputValue(),'Test Inn','Language switch must preserve unsubmitted translation');
      assert.equal(await editor.evaluate(el=>el.open),true,'Language switch must preserve editor disclosure');
      assert.equal(await editor.locator('input').evaluate(el=>document.activeElement===el),true,'Language switch must preserve translation focus');
    }
    await editor.locator('button').click();
    await page.waitForFunction(()=>flow.offline?.payload.translation_report.status==='complete' && document.getElementById('offline-preview').textContent.includes('Test Inn') && !document.querySelector('#place-translation-editor input'));
    assert.ok((await page.locator('#offline-preview').innerText()).includes('Test Inn'));
    assert.ok(!(await page.locator('#offline-preview').innerText()).includes('Unconfirmed place names'));
    assert.equal(await page.locator('#place-translation-editor input').count(),0);
    const files=[];
    for(const code of ['zh-CN','en','ja','ko']) {
      const html=await page.evaluate(code=>offlineDocument(flow.offline,code),code);
      assert.ok(!/<(?:script|link|img)\b/i.test(html));
      const file=path.join(output,`dynamic-place-${code}-2026-10-09.html`);fs.writeFileSync(file,html);files.push(file);
    }
    const offline=await context.newPage();await context.setOffline(true);
    await offline.goto('file:///'+files[1].replaceAll('\\','/'));
    assert.ok((await offline.locator('body').innerText()).includes('Test Inn'));
    await offline.locator('.offline-stop').nth(1).screenshot({path:path.join(output,'dynamic-offline-stations-en-2026-10-09.png')});
    await context.setOffline(false);
    await page.setViewportSize({width:390,height:844});
    await page.locator('#offline-panel').scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Mobile page must not overflow');
    await page.screenshot({path:path.join(output,'dynamic-place-mobile-2026-10-09.png')});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({days:3,language_switches:4,manual_confirmations:1,offline_exports:4,offline_open:true,mobile_overflow:false,browser_errors:errors,files},null,2));
  } finally {
    if(browser)await browser.close();
    const done=once(child,'exit');child.stdin.end();await done;
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
