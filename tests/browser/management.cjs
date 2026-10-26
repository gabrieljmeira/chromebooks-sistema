// Fluxos novos em banco temporário; nunca usa credenciais ou banco reais.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
(async () => {
  const server = spawn(process.env.PYTHON_BIN || 'python', [path.join(__dirname, 'server.py')], {stdio:['ignore','pipe','pipe']});
  let logs=''; server.stdout.on('data',d=>logs+=d); server.stderr.on('data',d=>logs+=d);
  let browser;
  try {
    let ready=false;
    for(let i=0;i<100;i++){
      try{if((await fetch('http://127.0.0.1:8765/saude')).ok){ready=true;break;}}catch{}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    assert.ok(ready,logs);
    browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || undefined,args:['--no-sandbox']});
    const context=await browser.newContext({viewport:{width:1280,height:900},locale:'pt-BR'});
    const page=await context.newPage(), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{const timer=window.setTimeout;window.setTimeout=(fn,delay,...args)=>timer(fn,delay===15000?400:delay,...args);});
    const base='http://127.0.0.1:8765';
    await page.goto(base+'/retirada');
    await page.locator('#name').fill('Professora Ana');
    await page.selectOption('#room','101');
    await page.locator('#quantity').fill('2');
    await page.selectOption('#kind','scheduled');
    await page.locator('#start_time').fill('11:00');
    await page.locator('#expected_return').fill('12:00');
    await page.getByRole('button',{name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();await page.waitForURL('**/enviado/1');
    await page.goto(base+'/admin/login');await page.locator('#password').fill('senha-teste-browser');
    await page.getByRole('button',{name:'Entrar',exact:true}).click();await page.waitForURL('**/admin');
    await page.goto(base+'/admin/inventario');
    const device=page.locator('article').filter({has:page.getByRole('heading',{name:'CH-020',exact:true})});
    await device.locator('summary').click();
    await device.locator('textarea').fill('Teclado com defeito, encaminhado para manutenção.');
    await device.getByRole('button',{name:'Registrar indisponibilidade'}).click();
    await page.waitForURL('**/admin/inventario');
    assert.match(await device.innerText(),/Indisponível/);
    const output=process.env.SCREENSHOT_DIR;if(output)fs.mkdirSync(output,{recursive:true});
    await page.setViewportSize({width:390,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(output)await page.screenshot({path:path.join(output,'inventario-390.png'),fullPage:true});
    await page.goto(base+'/admin/pedido/1/editar');
    await page.selectOption('#room','103');await page.locator('#start_time').fill('11:30');await page.locator('#expected_return').fill('12:30');
    await page.locator('#reason').fill('Professor pediu ajuste de sala e horário para esta aula.');
    await page.getByRole('button',{name:'Salvar alteração no histórico'}).click();await page.waitForURL('**/admin');
    assert.match(await page.locator('.loan-card').innerText(),/Sala 103/);
    await page.locator('[data-dashboard-tab=\"scheduled-loans\"]').click();await page.locator('#delivery-1 summary').click();
    assert.equal(await page.locator('#delivery-1 input[value="CH-020"]').count(),0);
    await page.locator('#delivery-1 input[value="CH-004"]').check();
    await page.waitForFunction(()=>!document.querySelector('#resume-updates').hidden);
    await page.locator('#resume-updates').click();
    await page.waitForFunction(()=>!document.querySelector('#delivery-1 input[value="CH-004"]').checked);
    await page.locator('#delivery-1 input[value="CH-004"]').check();await page.locator('#delivery-1 input[value="CH-005"]').check();
    await page.getByRole('button',{name:'Registrar entrega',exact:true}).click();await page.waitForURL('**/admin');
    await page.goto(base+'/admin/pedido/1/prorrogar');await page.locator('#expected_return').fill('13:00');await page.locator('#reason').fill('Aula estendida, sem conflito com outras reservas.');
    await page.getByRole('button',{name:'Salvar alteração no histórico'}).click();await page.waitForURL('**/admin');
    await page.goto(base+'/admin/pedido/1/corrigir');await page.selectOption('#code','CH-008');await page.selectOption('#state','active');await page.locator('#reason').fill('Código registrado incorretamente; aparelho físico é CH-008.');
    await page.getByRole('button',{name:'Salvar alteração no histórico'}).click();await page.waitForURL('**/admin');
    assert.match(await page.locator('.device-summary').innerText(),/CH-008/);
    await page.locator('[data-dashboard-tab=\"active-loans\"]').click();await page.locator('#return-1 summary').click();await page.locator('#return-1 input[value="CH-008"]').check();
    await page.getByRole('button',{name:'Registrar devolução',exact:true}).click();await page.waitForURL('**/admin');
    await page.goto(base+'/admin/pedido/1/corrigir');
    const option=page.locator('#allocation_id option').filter({hasText:'CH-008'});
    await page.selectOption('#allocation_id',await option.getAttribute('value'));
    await page.selectOption('#code','CH-008');await page.selectOption('#state','active');await page.locator('#reason').fill('Recebimento marcado por engano; aparelho segue com professor.');
    await page.getByRole('button',{name:'Salvar alteração no histórico'}).click();await page.waitForURL('**/admin');
    assert.equal(await page.locator('#return-1 input[name="devices"]').count(),2);
    await page.goto(base+'/admin/historico');await page.locator('.history-item summary').click();
    const history=await page.locator('.history-item').innerText();
    for(const label of ['Pedido alterado','Devolução prorrogada','Registro corrigido','CH-004','CH-008'])assert.ok(history.includes(label),label);
    if(output)await page.screenshot({path:path.join(output,'auditoria-390.png'),fullPage:true});
    const csvEvent=page.waitForEvent('download');await page.getByRole('link',{name:'Exportar resultado em CSV'}).click();
    const csv=await csvEvent;assert.equal(csv.suggestedFilename(),'historico-chromebooks.csv');
    assert.equal(await page.getByRole('link',{name:'Contas',exact:true}).count(),0);
    assert.equal((await page.request.get(base+'/admin/contas')).status(),404);
    for(const url of ['/admin','/admin/diagnostico','/admin/pedido/1/corrigir']){
      await page.goto(base+url);
      for(const width of [320,390,768,1280]){
        await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${url} ${width}`);
      }
    }
    await page.goto(base+'/admin/diagnostico');
    const backupEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Baixar backup completo'}).click();
    const backup=await backupEvent;
    const payload=JSON.parse(fs.readFileSync(await backup.path(),'utf8'));
    assert.equal(payload.format,'chromebooks-backup-v1');assert.equal(payload.tables.admin_users.length,0);
    assert.equal(payload.tables.unavailable_devices.length,1);
    await page.getByRole('button',{name:'Sair',exact:true}).click();await page.waitForURL('**/admin/login');
    assert.deepEqual(errors,[]);
    console.log('PASS: manutenção, edição, entrega, retomar atualização, prorrogação, correções auditadas, CSV, acesso administrativo, backup e telas 320–1280 px.');
  } finally {if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exit(1)});
