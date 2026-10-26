for (const field of document.querySelectorAll('input[inputmode="numeric"]')) {
  field.addEventListener('input', () => {
    const cursor = field.selectionStart ?? field.value.length;
    const before = field.value.slice(0, cursor).replace(/\D/g, '').length;
    const digits = field.value.replace(/\D/g, '').slice(0, 4);
    field.value = digits.length > 2 ? `${digits.slice(0, 2)}:${digits.slice(2)}` : digits;
    const position = Math.min(before + (before > 2 ? 1 : 0), field.value.length);
    field.setSelectionRange(position, position);
  });
}
const kind = document.getElementById('kind');
const start = document.getElementById('start_time');
function updateKind() {
  const scheduled = kind.value === 'scheduled';
  document.getElementById('start-field').hidden = !scheduled;
  start.disabled = !scheduled;
  start.required = scheduled;
  const date = document.getElementById("use_date");
  if(!date.value) date.value=date.min; date.disabled=!scheduled; date.required=scheduled;
}
kind.addEventListener('change', updateKind);
updateKind();

(() => {
  const form = document.getElementById('request-form');
  const room = document.getElementById('room');
  const end = document.getElementById('expected_return');
  const status = document.getElementById('room-status');
  const quantity = document.getElementById('quantity');
  const quantityStatus = document.getElementById('quantity-status');
  const availability = document.getElementById('device-availability');
  const summary = document.getElementById('availability-summary');
  const detail = document.getElementById('availability-detail');
  const options = [...room.options].filter(option => option.value);
  let controller, version = 0, timer, busy = new Set(), checked = false, available = null;
  function showAvailability(title, description, state = '') {
    summary.textContent = title; detail.textContent = description;
    availability.dataset.state = state;
  }
  function showQuantity() {
    quantity.max = String(available === null ? 20 : available);
    const exceeds = available !== null && Number(quantity.value) > available;
    const message = exceeds ? available === 0
      ? 'Nenhum Chromebook disponível. Escolha outro período.'
      : `Escolha no máximo ${available} ${available === 1 ? 'Chromebook' : 'Chromebooks'} ou altere o período.` : '';
    quantity.setCustomValidity(message);
    quantity.setAttribute('aria-invalid', String(exceeds));
    quantityStatus.textContent = message; quantityStatus.hidden = !exceeds;
    quantityStatus.className = exceeds ? 'hint danger-text' : 'hint';
  }
  function showSelection() {
    const occupied = checked && busy.has(room.value);
    room.setCustomValidity(occupied ? 'SALA EM USO: escolha outra sala ou outro horário.' : '');
    room.setAttribute('aria-invalid', String(occupied));
    if (checked) {
      status.className = occupied ? 'notice error' : 'hint';
      status.textContent = occupied ? 'SALA EM USO — existe outro pedido nesse intervalo ou uma devolução atrasada.'
        : room.value ? `Sala ${room.value} disponível no intervalo informado. Conferida novamente ao confirmar o envio.`
        : 'Selecione uma sala disponível para o intervalo informado.';
    }
  }
  function reset() {
    checked = false; busy = new Set(); available = null;
    for (const option of options) { option.disabled = false; option.textContent = `Sala ${option.value}`; }
    for (const option of (quantity.options || [])) option.disabled = false;
    showQuantity();
    room.setCustomValidity(''); room.setAttribute('aria-invalid', 'false'); status.className = 'hint';
  }
  async function check() {
    const currentVersion = ++version;
    controller?.abort();
    const refreshing = checked;
    if (!refreshing) reset();
    if (!end.value || !end.checkValidity() || (kind.value === 'scheduled' && (!start.value || !start.checkValidity()))) {
      reset();
      showAvailability('Disponibilidade de Chromebooks', 'Informe os horários para ver quantos estão disponíveis.');
      status.textContent = 'Informe os horários para consultar as salas disponíveis.'; return;
    }
    controller = new AbortController();
    if (!refreshing) {
      showAvailability('Consultando disponibilidade…', 'Verificando os Chromebooks para o período informado.');
      status.textContent = 'Consultando disponibilidade das salas…';
    }
    const params = new URLSearchParams({kind: kind.value, start_time: start.value, expected_return: end.value, use_date: document.getElementById("use_date").value});
    try {
      const response = await fetch(`${form.dataset.availabilityUrl}?${params}`, {cache:'no-store', signal:controller.signal});
      const data = await response.json();
      if (currentVersion !== version) return;
      if (!response.ok) {
        reset();
        const message = data.error || 'Confira os horários informados.';
        showAvailability('Disponibilidade não confirmada', message, 'error');
        status.textContent = message; return;
      }
      if (!Number.isInteger(data.available) || data.available < 0 || data.available > 20 || !Array.isArray(data.busy)) {
        throw new Error('Resposta de disponibilidade inválida');
      }
      available = data.available;
      showAvailability(available === 0 ? 'Nenhum Chromebook disponível' :
        `${available} ${available === 1 ? 'Chromebook disponível' : 'Chromebooks disponíveis'}`,
        available === 0 ? 'Escolha outro período para fazer o pedido.' : 'Para todo o período informado.',
        available === 0 ? 'empty' : '');
      for (const option of (quantity.options || [])) option.disabled = Number(option.value) > available;
      showQuantity();
      busy = new Set(data.busy); checked = true;
      for (const option of options) {
        const occupied = busy.has(option.value);
        option.disabled = occupied;
        option.textContent = `Sala ${option.value}${occupied ? ' — SALA EM USO' : ''}`;
      }
      showSelection();
    } catch (error) {
      if (currentVersion !== version || error.name === 'AbortError') return;
      reset();
      showAvailability('Consulta indisponível', 'A quantidade será conferida ao enviar o pedido.', 'error');
      status.textContent = 'Consulta indisponível. A sala será conferida ao enviar o pedido.';
    }
  }
  function schedule() {
    // Invalida imediatamente a resposta anterior, inclusive durante o debounce.
    version++; controller?.abort(); clearTimeout(timer); reset();
    showAvailability('Atualizando disponibilidade…', 'Conferindo o novo período informado.');
    status.textContent = 'Atualizando o intervalo…';
    timer = setTimeout(check, 250);
  }
  for (const field of [kind, start, end, document.getElementById("use_date")]) field.addEventListener('input', schedule);
  room.addEventListener('change', showSelection);
  quantity.addEventListener('change', showQuantity);
  quantity.addEventListener('input', showQuantity);
  for(const [id,delta] of [['quantity-minus',-1],['quantity-plus',1]]) document.getElementById(id).addEventListener('click',()=>{const next=Number(quantity.value)+delta;const max=available===null?20:available;if(Number.isInteger(next)&&next>=1&&next<=max){quantity.value=next;showQuantity();}});
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  setInterval(() => { if (!document.hidden) check(); }, 30000);
  check();
})();
