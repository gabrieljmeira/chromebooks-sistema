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
}
kind.addEventListener('change', updateKind);
updateKind();

(() => {
  const form = document.getElementById('request-form');
  const room = document.getElementById('room');
  const end = document.getElementById('expected_return');
  const status = document.getElementById('room-status');
  const options = [...room.options].filter(option => option.value);
  let controller, version = 0, timer, busy = new Set(), checked = false;
  function showSelection() {
    const occupied = checked && busy.has(room.value);
    room.setCustomValidity(occupied ? 'SALA EM USO: escolha outra sala ou outro horário.' : '');
    room.setAttribute('aria-invalid', String(occupied));
    if (checked) {
      status.className = occupied ? 'notice error' : 'hint';
      status.textContent = occupied ? 'SALA EM USO — existe outro pedido nesse intervalo ou uma devolução atrasada.'
        : room.value ? `Sala ${room.value} disponível no intervalo informado. A confirmação ocorre ao enviar.`
        : 'Selecione uma sala disponível para o intervalo informado.';
    }
  }
  function reset() {
    checked = false; busy = new Set();
    for (const option of options) { option.disabled = false; option.textContent = `Sala ${option.value}`; }
    room.setCustomValidity(''); room.setAttribute('aria-invalid', 'false'); status.className = 'hint';
  }
  async function check() {
    const currentVersion = ++version;
    controller?.abort();
    reset();
    if (!end.value || !end.checkValidity() || (kind.value === 'scheduled' && (!start.value || !start.checkValidity()))) {
      status.textContent = 'Informe os horários para consultar as salas disponíveis.'; return;
    }
    controller = new AbortController();
    status.textContent = 'Consultando disponibilidade das salas…';
    const params = new URLSearchParams({kind: kind.value, start_time: start.value, expected_return: end.value});
    try {
      const response = await fetch(`${form.dataset.availabilityUrl}?${params}`, {cache:'no-store', signal:controller.signal});
      const data = await response.json();
      if (currentVersion !== version) return;
      if (!response.ok) { status.textContent = data.error || 'Confira os horários informados.'; return; }
      busy = new Set(data.busy); checked = true;
      for (const option of options) {
        const occupied = busy.has(option.value);
        option.disabled = occupied;
        option.textContent = `Sala ${option.value}${occupied ? ' — SALA EM USO' : ''}`;
      }
      showSelection();
    } catch (error) {
      if (currentVersion !== version || error.name === 'AbortError') return;
      status.textContent = 'Consulta indisponível. A sala será conferida ao enviar o pedido.';
    }
  }
  function schedule() {
    // Invalida imediatamente a resposta anterior, inclusive durante o debounce.
    version++; controller?.abort(); clearTimeout(timer); reset();
    status.textContent = 'Atualizando o intervalo…';
    timer = setTimeout(check, 250);
  }
  for (const field of [kind, start, end]) field.addEventListener('input', schedule);
  room.addEventListener('change', showSelection);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  setInterval(() => { if (!document.hidden) check(); }, 30000);
  check();
})();
