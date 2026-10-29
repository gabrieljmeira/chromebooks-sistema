// Inicia seu próprio servidor com banco temporário; não acessa produção.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
(async () => {
  const server = spawn(process.env.PYTHON_BIN || 'python', [path.join(__dirname,'server.py')], {stdio:['ignore','pipe','pipe']});
  let logs=''; server.stdout.on('data',d=>logs+=d); server.stderr.on('data',d=>logs+=d);
  let ready=false;
  for(let i=0;i<100;i++){
    try{const response=await fetch('http://127.0.0.1:8765/retirada');if(response.ok){ready=true;break;}}catch{}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!ready){server.kill();throw new Error('Servidor indisponível: '+logs);}
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || undefined, args:['--no-sandbox']});
  const output = process.env.SCREENSHOT_DIR;
  if (output) fs.mkdirSync(output,{recursive:true});
  try {
    const context = await browser.newContext({viewport:{width:1280,height:900},locale:'pt-BR'});
    const page = await context.newPage(), errors = [];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error' && !m.text().includes('status of 422')) errors.push(m.text());});
    // Acelera somente o polling para testar preservação de edição sem esperar 15s.
    await page.addInitScript(() => {
      const original = window.setTimeout;
      window.setTimeout = (fn, delay, ...args) => original(fn, delay===15000 ? 500 : delay,...args);
    });
    const base='http://127.0.0.1:8765';
    const openForm=()=>page.goto(base+'/retirada');
    const set=(id,value)=>page.locator('#'+id).fill(value);
    await openForm();
    assert.equal(await page.locator('#room option').count(),26);
    assert.equal(await page.locator('#room option[value="2010"]').count(),0);
    await set('name','Professora Ana');await page.locator('#quantity').fill('2');
    await page.selectOption('#room','210');await set('expected_return','11:00');
    await page.waitForFunction(()=>document.querySelector('#room-status').textContent.includes('disponível no intervalo'));
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();await page.waitForURL('**/enviado/1');
    await openForm();await set('name','Professor Bruno');await page.selectOption('#room','210');await set('expected_return','10:30');
    await page.waitForFunction(()=>document.querySelector('#room-status').textContent.includes('SALA EM USO'));
    assert.equal(await page.locator('#room option[value="210"]').isDisabled(),true);
    assert.equal(await page.locator('#room').evaluate(el=>el.checkValidity()),false);
    await page.selectOption('#kind','scheduled');await set('start_time','11:00');await set('expected_return','12:00');
    await page.waitForFunction(()=>document.querySelector('#room-status').textContent.includes('disponível no intervalo'));
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();await page.waitForURL('**/enviado/2');
    await openForm();await set('name','Professora Carla');await page.selectOption('#room','101');await set('expected_return','10:05');
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();await page.waitForURL('**/enviado/3');
    await page.goto(base+'/admin/login');await page.locator('[name="password"]').fill('senha-teste-browser');
    await page.getByRole('button',{name:'Entrar'}).click();await page.waitForURL('**/admin');
    assert.equal(await page.locator('#pending-loans .loan-card').count(),2);
    await page.locator('[data-dashboard-tab=\"pending-loans\"]').click();await page.locator('#delivery-1 summary').click();
    await page.locator('#delivery-1 input[value="CH-004"]').check();
    assert.equal(await page.locator('#delivery-1 .selection-count').innerText(),'1 de 2 aparelhos selecionados.');
    assert.equal(await page.locator('#delivery-1 form').first().evaluate(el=>el.checkValidity()),false);
    await page.waitForFunction(()=>document.querySelector('#sync-status').textContent.includes('Seleção preservada'));
    assert.equal(await page.locator('#delivery-1 input[value="CH-004"]').isChecked(),true);
    await page.locator('#delivery-1 input[value="CH-015"]').check();
    await page.locator('#delivery-1').getByRole('button',{name:'Registrar entrega'}).click();await page.waitForURL('**/admin');
    await page.locator('[data-dashboard-tab=\"active-loans\"]').click();await page.locator('#return-1 summary').click();await page.locator('#return-1 input[value="CH-015"]').check();
    await page.locator('#return-1').getByRole('button',{name:'Registrar devolução'}).click();await page.waitForURL('**/admin');
    assert.equal(await page.locator('#return-1 input[name="devices"]').count(),1);
    assert.deepEqual((await (await page.request.get(base+'/salas/disponibilidade?kind=now&expected_return=10:30')).json()).busy,['101','210']);
    await page.locator('[data-dashboard-tab=\"active-loans\"]').click();await page.locator('#return-1 summary').click();await page.locator('#return-1 input[value="CH-004"]').check();
    await page.locator('#return-1').getByRole('button',{name:'Registrar devolução'}).click();await page.waitForURL('**/admin');
    assert.deepEqual((await (await page.request.get(base+'/salas/disponibilidade?kind=now&expected_return=10:30')).json()).busy,['101']);
    await page.locator('[data-dashboard-tab=\"pending-loans\"]').click();await page.locator('#delivery-3 summary').click();await page.locator('#delivery-3 input[value="CH-007"]').check();
    await page.locator('#delivery-3').getByRole('button',{name:'Registrar entrega'}).click();await page.waitForURL('**/admin');
    await page.waitForFunction(()=>document.querySelector('#alerts').textContent.includes('5 minutos'));
    assert.equal(await page.locator('.due-soon').count(),1);
    await page.locator('h1').click();
    await page.waitForFunction(()=>document.querySelector('#sound-status').textContent.includes('ativado'));
    await page.locator('#sound-toggle').click();
    assert.match(await page.locator('#sound-status').innerText(),/silenciado/);
    await page.reload();assert.match(await page.locator('#sound-status').innerText(),/silenciado/);
    for (const width of [320,360,390,412,768,1280]) {
      await page.setViewportSize({width,height:900});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`painel overflow ${width}`);
      if(output && [390,1280].includes(width)) await page.screenshot({path:path.join(output,`painel-${width}.png`),fullPage:true});
    }
    await page.goto(base+'/admin/historico');
    await page.selectOption('#history-room','210');await page.locator('#history-date').fill('2026-10-19');await page.selectOption('#history-status','returned');
    await page.getByRole('button',{name:'Filtrar',exact:true}).click();
    assert.equal(await page.locator('.history-item').count(),1);
    assert.match(await page.locator('.history-item').innerText(),/Professora Ana/);
    await page.locator('.history-item summary').click();
    assert.match(await page.locator('.history-item').innerText(),/CH-004/);
    assert.match(await page.locator('.history-item').innerText(),/19\/10\/2026 10:00/);
    await page.setViewportSize({width:390,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'histórico overflow');
    if(output) await page.screenshot({path:path.join(output,'historico-390.png'),fullPage:true});
    await openForm();
    for(const width of [320,390,768,1280]){
      await page.setViewportSize({width,height:900});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`formulário overflow ${width}`);
    }
    if(output) await page.screenshot({path:path.join(output,'pedido-1280.png'),fullPage:true});
    // Sem JavaScript, o servidor continua impedindo o conflito e renderiza o erro.
    const noJs=await browser.newContext({javaScriptEnabled:false});const plain=await noJs.newPage();
    await plain.goto(base+'/retirada');await plain.locator('#name').fill('Professor sem JS');await plain.selectOption('#room','101');await plain.locator('#expected_return').fill('10:04');
    await plain.getByRole('button',{name:'Enviar pedido à TI'}).click();
    assert.match(await plain.locator('.notice.error').innerText(),/Sala ou quantidade indisponível/);
    await noJs.close();
    assert.deepEqual(errors,[]);
    console.log('PASS: pedidos imediato/agendado, salas, entrega, devolução parcial/completa, polling, som, histórico, sem JS e layouts 320–1280 px.');
  } finally { await browser.close(); server.kill(); }
})().catch(error=>{console.error(error);process.exit(1)});
