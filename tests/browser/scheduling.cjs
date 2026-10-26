const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const path = require('node:path');
(async()=>{
  const server=spawn(process.env.PYTHON_BIN||'python',[path.join(__dirname,'server.py')]);
  let logs='',browser;server.stderr.on('data',d=>logs+=d);
  const base='http://127.0.0.1:8765';
  try{
    let ready=false;for(let n=0;n<100;n++){try{if((await fetch(base+'/retirada')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}assert.ok(ready,logs);
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({locale:'pt-BR'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/retirada');await page.locator('#name').fill('Professora Ana');
    await page.selectOption('#kind','scheduled');await page.locator('#use_date').fill('2026-10-21');
    await page.locator('#start_time').fill('08:00');await page.locator('#expected_return').fill('09:00');
    await page.locator('#quantity').fill('6');await page.selectOption('#room','107');
    await page.waitForFunction(()=>document.querySelector('#availability-summary').textContent.includes('20 Chromebooks'));
    for(const width of [320,390,768,1024,1280]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`form ${width}`);}
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();assert.match(await page.locator('main').innerText(),/21\/10\/2026/);
    await page.getByRole('button',{name:'Voltar e editar'}).click();assert.equal(await page.locator('#use_date').inputValue(),'2026-10-21');
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();await page.waitForURL('**/enviado/1');
    await page.goto(base+'/admin/login');await page.locator('[name=password]').fill('senha-teste-browser');await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.waitForURL('**/admin');
    assert.equal(await page.locator('#pending-loans .loan-card').count(),0);
    await page.locator('[data-dashboard-tab="scheduled-loans"]').click();assert.equal(await page.locator('#scheduled-loans .loan-card').count(),1);
    assert.match(await page.locator('#scheduled-loans').innerText(),/21\/10\/2026/);
    for(const width of [320,390,768,1024,1280]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`admin ${width}`);}
    assert.deepEqual(errors,[]);console.log('PASS: future schedule, review/edit/confirm, TI dates and layouts 320–1280.');
  }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
