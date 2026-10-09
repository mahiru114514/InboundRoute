"use strict";
// Isolated HTTP server and browser profile; never touches the user's trip data.
// node tools/verify_onboarding_browser.cjs <playwright module directory> [browser executable]
const {chromium}=require(process.argv[2] || 'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const root=path.resolve(__dirname,'..');
const python=process.env.ONBOARDING_TEST_PYTHON || 'python';
const script=[
  'import sys, tempfile, threading',
  'from pathlib import Path',
  'from modules.web_workbench.engine import build_server',
  'from modules.web_workbench.proxy import ServiceRegistry',
  'with tempfile.TemporaryDirectory() as folder:',
  '    server=build_server(ServiceRegistry(Path(folder)), "isolated-guide-token", 0, maps={"provider":"none", "ready":False})',
  '    threading.Thread(target=server.serve_forever, daemon=True).start()',
  '    print(server.server_port, flush=True)',
  '    sys.stdin.read()',
  '    server.shutdown()',
  '    server.server_close()',
].join('\n');

(async()=>{
  const child=spawn(python,['-u','-c',script],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
  let browser;
  try {
    const port=await new Promise((resolve,reject)=>{
      child.once('error',reject);child.once('exit',code=>reject(Error(`server exited ${code}`)));
      child.stderr.on('data',data=>process.stderr.write(data));
      let output='';child.stdout.on('data',data=>{output+=data;if(output.includes('\n'))resolve(Number(output.trim()));});
    });
    assert.ok(port>0);
    browser=await chromium.launch({headless:true,...(process.argv[3]?{executablePath:process.argv[3]}:{})});
    const context=await browser.newContext({locale:'zh-CN',viewport:{width:1280,height:800}});
    const page=await context.newPage();
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`http://127.0.0.1:${port}/`);
    await page.waitForSelector('#onboarding-dialog[open]');
    await page.evaluate(()=>window.__workbenchBoot);
    assert.equal(await page.locator('#onboarding-progress').textContent(),'1 / 5');
    // Chapter navigation, native FAQs and long-text scrolling work in the real browser.
    await page.locator('#onboarding-chapter-3').click();
    assert.equal(await page.locator('#onboarding-progress').textContent(),'4 / 5');
    await page.locator('#onboarding-question-1').click();
    await page.locator('#onboarding-question-2').click();
    assert.equal(await page.locator('#onboarding-faq-1').getAttribute('open'),'');
    await page.evaluate(()=>{document.getElementById('onboarding-content').scrollTop=100;window.IRLanguage.setLanguage('en');});
    assert.equal(await page.locator('#onboarding-faq-1').getAttribute('open'),'');
    assert.equal(await page.evaluate(()=>document.getElementById('onboarding-content').scrollTop),100);
    assert.ok(!/[\u4e00-\u9fff]/.test(await page.locator('#onboarding-dialog').innerText()));
    await page.locator('#onboarding-chapter-0').click();
    assert.equal(await page.locator('#onboarding-faq-1').getAttribute('open'),null);
    assert.equal(await page.evaluate(()=>document.getElementById('onboarding-content').scrollTop),0);
    await page.evaluate(()=>window.IRLanguage.setLanguage('zh-CN'));
    assert.equal(await page.locator('#onboarding-prev').isDisabled(),true);
    const shots=path.join(root,'docs','onboarding-preview');fs.mkdirSync(shots,{recursive:true});
    fs.writeFileSync(path.join(shots,'onboarding-desktop-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
    // Tab may move to browser chrome (body), but never to background controls.
    for(let i=0;i<8;i++) {
      await page.keyboard.press(i<4?'Tab':'Shift+Tab');
      assert.equal(await page.evaluate(()=>document.activeElement===document.body || !!document.activeElement.closest('#onboarding-dialog')),true);
    }
    await page.locator('#onboarding-skip').click();
    await page.waitForFunction(()=>!document.getElementById('onboarding-dialog').open);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'onboarding-open');
    await page.locator('#duration-days').fill('7');
    await page.locator('#onboarding-open').click();
    await page.locator('#onboarding-next').click();
    await page.locator('#onboarding-prev').click();
    assert.equal(await page.locator('#onboarding-progress').textContent(),'1 / 5');
    // Language switching while open keeps the current page and fully updates text/labels.
    for(const code of ['en','ja','ko','zh-CN']) {
      await page.evaluate(code=>window.IRLanguage.setLanguage(code),code);
      for(let i=0;i<5;i++) {
        await page.locator('#onboarding-question-1').click();
        await page.locator('#onboarding-question-2').click();
        const text=await page.locator('#onboarding-dialog').innerText();
        if(code==='en')assert.ok(!/[\u4e00-\u9fff]/.test(text),text);
        assert.equal(await page.locator('#onboarding-progress').textContent(),`${i+1} / 5`);
        if(i<4)await page.locator('#onboarding-next').click();
      }
      await page.keyboard.press('Escape');
      await page.waitForFunction(()=>!document.getElementById('onboarding-dialog').open);
      assert.equal(await page.locator('#duration-days').inputValue(),'7','Guide preserves the setup draft');
      await page.locator('#onboarding-open').click();
    }
    for(let i=0;i<5;i++)await page.locator('#onboarding-next').click();
    await page.waitForFunction(()=>!document.getElementById('onboarding-dialog').open);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'setup-panel');
    assert.equal(await page.locator('#setup-disclosure').getAttribute('open'),'');
    await page.reload();await page.evaluate(()=>window.__workbenchBoot);
    assert.equal(await page.locator('#onboarding-dialog').getAttribute('open'),null,'Seen guide stays closed on refresh');
    await page.locator('#onboarding-open').click();
    assert.equal(await page.locator('#onboarding-progress').textContent(),'1 / 5');
    await page.keyboard.press('Escape');
    // Narrow/short screens must keep every action visible and avoid horizontal overflow.
    for(const viewport of [{width:390,height:844},{width:320,height:568},{width:667,height:320}]) {
      await page.setViewportSize(viewport);
      await page.locator('#onboarding-open').click();
      await page.evaluate(()=>window.IRLanguage.setLanguage('en'));
      const geometry=await page.evaluate(()=>{
        const dialog=document.getElementById('onboarding-dialog'),actions=document.querySelector('.onboarding-actions');
        const box=dialog.getBoundingClientRect(),footer=actions.getBoundingClientRect();
        return {x:box.x,right:box.right,bottom:box.bottom,footerTop:footer.top,footerBottom:footer.bottom,innerHeight,innerWidth,overflow:dialog.scrollWidth>dialog.clientWidth};
      });
      assert.ok(geometry.x>=0 && geometry.right<=viewport.width && geometry.bottom<=viewport.height,JSON.stringify(geometry));
      assert.ok(geometry.footerTop>=0 && geometry.footerBottom<=viewport.height && !geometry.overflow,JSON.stringify(geometry));
      assert.equal(await page.evaluate(()=>{const body=document.getElementById('onboarding-content');return body.scrollHeight>body.clientHeight;}),true,'Detailed text scrolls inside the dialog');
      await page.locator('#onboarding-chapter-4').click();
      assert.equal(await page.locator('#onboarding-progress').textContent(),'5 / 5');
      await page.locator('#onboarding-question-2').click();
      await page.evaluate(()=>{const body=document.getElementById('onboarding-content');body.scrollTop=body.scrollHeight;});
      for(const id of ['onboarding-skip','onboarding-prev','onboarding-next']) {
        const box=await page.locator('#'+id).boundingBox();assert.ok(box.x>=0 && box.x+box.width<=viewport.width && box.y+box.height<=viewport.height,JSON.stringify(box));
      }
      if(viewport.width===390) {
        fs.writeFileSync(path.join(shots,'onboarding-mobile-en-faq-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
        await page.locator('#onboarding-chapter-0').click();
        fs.writeFileSync(path.join(shots,'onboarding-mobile-en-2026-10-08.png'),await page.screenshot({animations:'disabled'}));
      }
      await page.keyboard.press('Escape');
    }
    assert.deepEqual(errors,[],'No browser JavaScript errors');
    // Denied storage still permits first display, skipping and manual replay.
    const denied=await browser.newContext({locale:'zh-CN'});
    await denied.addInitScript(()=>{
      Storage.prototype.getItem=function(){throw new DOMException('Denied','SecurityError');};
      Storage.prototype.setItem=function(){throw new DOMException('Denied','SecurityError');};
    });
    const deniedPage=await denied.newPage();
    await deniedPage.goto(`http://127.0.0.1:${port}/`);
    await deniedPage.waitForSelector('#onboarding-dialog[open]');
    await deniedPage.locator('#onboarding-skip').click();
    await deniedPage.locator('#onboarding-open').click();
    assert.equal(await deniedPage.locator('#onboarding-progress').textContent(),'1 / 5');
    await denied.close();
    console.log('Browser onboarding checks passed: 4 languages, first visit, skip, replay, completion, refresh, draft preservation, Escape, keyboard focus, denied storage; desktop and 3 mobile/short viewports.');
  } finally {
    if(browser)await browser.close();
    const closed=once(child,'exit');child.stdin.end();await closed;
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
