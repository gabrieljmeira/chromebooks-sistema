// Exercita o formulário e a API reais em SQLite temporário, sem acessar produção.
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
      try { if ((await fetch(base + '/retirada')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, logs);
    browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || undefined, args:['--no-sandbox']});
    const page = await browser.newPage({viewport:{width:390,height:844},locale:'pt-BR'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const summary = page.locator('#availability-summary');
    const expectCount = count => page.waitForFunction(count => {
      const text = document.querySelector('#availability-summary').textContent;
      return count === 0 ? text === 'Nenhum Chromebook disponível' : text.startsWith(`${count} Chromebook`);
    }, count);
    await page.goto(base + '/retirada');
    assert.match(await summary.innerText(), /Disponibilidade de Chromebooks/);
    await page.locator('#name').fill('Professora Ana');
    await page.selectOption('#room', '101');
    await page.locator('#expected_return').fill('11:00');
    await expectCount(20);
    await page.locator('#quantity').fill('12');
    await page.getByRole('button', {name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();
    await page.waitForURL('**/enviado/1');
    await page.goto(base + '/retirada');
    // Uma seleção anterior excessiva é preservada e sinalizada, nunca reduzida silenciosamente.
    await page.locator('#quantity').fill('20');
    await page.locator('#expected_return').fill('10:30');
    await expectCount(8);
    assert.equal(await page.locator('#quantity').inputValue(), '20');
    assert.equal(await page.locator('#quantity').getAttribute('max'), '8');
    assert.equal(await page.locator('#quantity').evaluate(el => el.checkValidity()), false);
    assert.match(await page.locator('#quantity-status').innerText(), /no máximo 8/);
    await page.locator('#quantity').fill('8');
    assert.equal(await page.locator('#quantity').evaluate(el => el.checkValidity()), true);
    await page.selectOption('#kind', 'scheduled');
    await page.locator('#start_time').fill('11:00');
    await page.locator('#expected_return').fill('12:00');
    await expectCount(20);
    assert.equal(await page.locator('#quantity').getAttribute('max'), '20');
    await page.locator('#name').fill('Professor Bruno');
    await page.selectOption('#room', '103');
    await page.locator('#quantity').fill('20');
    await page.getByRole('button', {name:'Enviar pedido à TI'}).click();await page.getByRole('button',{name:'Confirmar envio'}).click();
    await page.waitForURL('**/enviado/2');
    await page.goto(base + '/retirada');
    await page.locator('#expected_return').fill('11:30');
    await expectCount(0);
    assert.equal(await page.locator('#quantity').evaluate(el => el.checkValidity()), false);
    assert.equal(await page.locator('#quantity').getAttribute('max'), '0');
    await page.locator('#expected_return').fill('');
    await page.waitForFunction(() => document.querySelector('#availability-summary').textContent === 'Disponibilidade de Chromebooks');
    assert.equal(await page.locator('#quantity').getAttribute('max'), '20');
    await page.locator('#expected_return').fill('09:00');
    await page.waitForFunction(() => document.querySelector('#device-availability').dataset.state === 'error');
    assert.match(await page.locator('#availability-detail').innerText(), /posterior/);
    await page.locator('#expected_return').fill('10:30');
    await expectCount(8);
    // Não reaproveita contagens antigas se a consulta falhar.
    await page.route('**/salas/disponibilidade?*', route => route.abort());
    await page.locator('#expected_return').fill('10:45');
    await page.waitForFunction(() => document.querySelector('#availability-summary').textContent === 'Consulta indisponível');
    assert.equal(await page.locator('#quantity').getAttribute('max'), '20');
    assert.match(await page.locator('#availability-detail').innerText(), /conferida ao enviar/);
    await page.unroute('**/salas/disponibilidade?*');
    // Uma resposta atrasada não pode sobrescrever um novo horário.
    let release, entered;
    const started = new Promise(resolve => entered = resolve);
    const gate = new Promise(resolve => release = resolve);
    await page.route('**/salas/disponibilidade?*', async route => {
      if (new URL(route.request().url()).searchParams.get('expected_return') === '10:40') {
        entered(); await gate;
        await route.fulfill({json:{busy:[],available:1}});
      } else await route.continue();
    });
    await page.locator('#expected_return').fill('10:40');
    await started;
    await page.locator('#expected_return').fill('10:30');
    await expectCount(8);
    release();
    await page.unrouteAll({behavior:'wait'});
    assert.match(await summary.innerText(), /^8 Chromebooks disponíveis$/);
    const output = process.env.SCREENSHOT_DIR;
    if (output) fs.mkdirSync(output, {recursive:true});
    for (const width of [320,360,390,412,768,1280]) {
      await page.setViewportSize({width,height:844});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow ${width}`);
      const bounds = await page.locator('#device-availability').boundingBox();
      assert.ok(bounds.width <= width && bounds.height < 150, `resumo compacto ${width}`);
      if (output && [390,1280].includes(width)) await page.screenshot({path:path.join(output,`disponibilidade-${width}.png`),fullPage:true});
    }
    assert.deepEqual(errors, []);
    console.log('PASS: estoque por período, limites de quantidade, falta de estoque, horários inválidos, falha de rede, resposta atrasada e layouts 320–1280 px.');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exit(1); });
