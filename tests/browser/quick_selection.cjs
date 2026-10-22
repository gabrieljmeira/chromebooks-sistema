// Testa seleção e entrega em banco temporário; nunca acessa produção.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

(async () => {
  const server = spawn(process.env.PYTHON_BIN || 'python', [path.join(__dirname, 'server.py')], {stdio:['ignore','pipe','pipe']});
  let logs = '', browser;
  server.stdout.on('data', data => logs += data);
  server.stderr.on('data', data => logs += data);
  const base = 'http://127.0.0.1:8765';
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      try { if ((await fetch(base + '/saude')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, logs);
    browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || undefined, args:['--no-sandbox']});
    const context = await browser.newContext({viewport:{width:390,height:844},locale:'pt-BR'});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      const timeout = window.setTimeout;
      window.setTimeout = (fn, delay, ...args) => timeout(fn, delay === 15000 ? 500 : delay, ...args);
    });
    const ask = async (room, quantity, id) => {
      await page.goto(base + '/retirada');
      await page.locator('#name').fill('Professor de teste');
      await page.selectOption('#quantity', String(quantity));
      await page.selectOption('#room', room);
      await page.locator('#expected_return').fill('12:00');
      await page.getByRole('button', {name:'Enviar pedido à TI'}).click();
      await page.waitForURL(`**/enviado/${id}`);
    };
    const checked = selector => page.locator(selector + ' input[name="devices"]:checked').evaluateAll(boxes => boxes.map(box => box.value));
    await ask('101', 2, 1);
    await ask('103', 10, 2);
    await page.goto(base + '/admin/login');
    await page.locator('#password').fill('senha-teste-browser');
    await page.getByRole('button', {name:'Entrar',exact:true}).click();
    await page.waitForURL('**/admin');
    await page.locator('#delivery-1 summary').click();
    await page.locator('#delivery-1 input[value="CH-004"]').check();
    await page.locator('#delivery-1 input[value="CH-008"]').check();
    await page.locator('#delivery-1').getByRole('button', {name:'Registrar entrega',exact:true}).click();
    await page.waitForURL('**/admin');
    await page.locator('#delivery-2 summary').click();
    await page.locator('#delivery-2').getByRole('button', {name:'Selecionar 10 disponíveis',exact:true}).click();
    const expected = [1,2,3,5,6,7,9,10,11,12].map(n => `CH-${String(n).padStart(3,'0')}`);
    assert.deepEqual(await checked('#delivery-2'), expected);
    assert.equal(await page.locator('#delivery-2 .selection-count').innerText(), '10 de 10 aparelhos selecionados.');
    assert.equal(await page.locator('#delivery-2 form').first().evaluate(form => form.checkValidity()), true);
    assert.deepEqual(await checked('#return-1'), []);
    // O atalho apenas marca: o pedido continua pendente e nenhuma entrega é gravada.
    assert.equal(await page.locator('#pending-loans .loan-card').count(), 1);
    assert.equal(await page.locator('#active-loans .loan-card').count(), 1);
    // Remove o foco do formulário: somente o evento de edição impede o polling de apagar a seleção.
    await page.locator('h1').click();
    await page.waitForFunction(() => document.querySelector('#sync-status').textContent.includes('Seleção preservada'));
    assert.deepEqual(await checked('#delivery-2'), expected);
    await page.locator('#delivery-2 input[value="CH-012"]').uncheck();
    await page.locator('#delivery-2 input[value="CH-013"]').check();
    assert.ok((await checked('#delivery-2')).includes('CH-013'));
    await page.locator('#delivery-2 [data-select-available]').click();
    assert.deepEqual(await checked('#delivery-2'), expected);
    const output = process.env.SCREENSHOT_DIR;
    if (output) fs.mkdirSync(output, {recursive:true});
    for (const width of [320,360,390,412,768,1280]) {
      await page.setViewportSize({width,height:844});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow ${width}`);
      const bounds = await page.locator('#delivery-2 [data-select-available]').boundingBox();
      assert.ok(bounds.width <= width && bounds.height >= 44, `botão acessível ${width}`);
      if (output && [390,1280].includes(width)) await page.locator('#delivery-2').screenshot({path:path.join(output,`selecao-rapida-${width}.png`)});
    }
    await page.locator('#delivery-2').getByRole('button', {name:'Registrar entrega',exact:true}).click();
    await page.waitForURL('**/admin');
    assert.deepEqual(await page.locator('#return-2 input[name="devices"]').evaluateAll(boxes => boxes.map(box => box.value)), expected);
    assert.equal(await page.locator('#return-2 [data-select-available]').count(), 0);
    // Se o estoque mudar depois de marcar, a confirmação continua sendo validada no servidor.
    await ask('105', 8, 3);
    await page.goto(base + '/admin');
    await page.locator('#delivery-3 summary').click();
    await page.locator('#delivery-3 [data-select-available]').click();
    assert.equal((await checked('#delivery-3')).length, 8);
    const inventory = await context.newPage();
    await inventory.goto(base + '/admin/inventario');
    const device = inventory.locator('article').filter({has:inventory.getByRole('heading', {name:'CH-020',exact:true})});
    await device.locator('summary').click();
    await device.locator('textarea').fill('Teclado com defeito, aparelho em manutenção.');
    await device.getByRole('button', {name:'Registrar indisponibilidade',exact:true}).click();
    await inventory.waitForURL('**/admin/inventario');
    await page.locator('#delivery-3').getByRole('button', {name:'Registrar entrega',exact:true}).click();
    await page.waitForURL('**/admin');
    assert.ok(await page.locator('.notice.error').count());
    assert.equal(await page.locator('#delivery-3').count(), 1);
    await page.locator('#delivery-3 summary').click();
    assert.equal(await page.locator('#delivery-3 [data-select-available]').isDisabled(), true);
    assert.equal(await page.locator('#delivery-3 input[value="CH-020"]').count(), 0);
    assert.match(await page.locator('#delivery-3 .quick-selection-help').innerText(), /Há 7 disponíveis; este pedido precisa de 8/);
    assert.equal(await page.locator('#return-3').count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: seleção numérica pulando 004/008, ajuste manual, nenhuma entrega automática, polling, revalidação após manutenção, estoque insuficiente e telas de 320–1280 px.');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exit(1); });
