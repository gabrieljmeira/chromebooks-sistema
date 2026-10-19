(() => {
  const content = document.getElementById('dashboard-content');
  const status = document.getElementById('sync-status');
  const alertBox = document.getElementById('alerts');
  const soundStatus = document.getElementById('sound-status');
  const soundToggle = document.getElementById('sound-toggle');
  let audio = null, dirty = false, stopped = false, queuedSound = false;
  let muted = false;
  try { muted = localStorage.getItem('chromebooks:sound-muted') === '1'; } catch {}
  const memory = new Set();
  function showSound() {
    soundStatus.textContent = muted ? 'Som silenciado. Os avisos visuais continuam ativos.' : audio?.state === 'running'
      ? 'Som dos avisos ativado.' : 'Clique no painel para liberar o som dos avisos.';
    if (soundToggle) {
      soundToggle.textContent = muted || audio?.state !== 'running' ? 'Ativar som' : 'Silenciar som';
      soundToggle.setAttribute('aria-pressed', String(!muted && audio?.state === 'running'));
    }
  }
  function beep() {
    if (muted || stopped) { queuedSound = false; return; }
    if (!audio || audio.state !== 'running') { queuedSound = true; showSound(); return; }
    queuedSound = false;
    // Toque original em duas frases ascendentes, com ataque suave e cauda de sino.
    for (const [offset, frequency] of [[0, 880], [0.16, 1174.66], [0.34, 1567.98],
                                      [0.95, 880], [1.11, 1174.66], [1.29, 1567.98]]) {
      const tone = audio.createOscillator(), gain = audio.createGain();
      const begin = audio.currentTime + offset;
      tone.type = 'sine'; tone.frequency.value = frequency;
      tone.connect(gain); gain.connect(audio.destination);
      gain.gain.setValueAtTime(0.001, begin);
      gain.gain.exponentialRampToValueAtTime(0.26, begin + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.001, begin + 0.55);
      tone.start(begin); tone.stop(begin + 0.56);
      tone.onended = () => { tone.disconnect(); gain.disconnect(); };
    }
  }
  async function unlockAudio() {
    if (stopped || muted || audio?.state === 'running') return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!audio) { audio = new Audio(); audio.onstatechange = showSound; }
      await audio.resume();
      if (muted || stopped) return;
      showSound();
      if (queuedSound && audio.state === 'running') beep();
    } catch {
      soundStatus.textContent = 'Áudio bloqueado. Confira as permissões de som do navegador.';
    }
  }
  document.addEventListener('click', unlockAudio);
  document.addEventListener('keydown', event => {
    if (event.target !== soundToggle) unlockAudio();
  });
  soundToggle?.addEventListener('click', async event => {
    event.stopPropagation();
    muted = !muted && audio?.state === 'running';
    if (muted) { queuedSound = false; await audio.suspend(); }
    try { localStorage.setItem('chromebooks:sound-muted', muted ? '1' : '0'); } catch {}
    if (!muted) await unlockAudio();
    showSound();
  });
  content.addEventListener('change', () => { dirty = true; });
  content.addEventListener('input', () => { dirty = true; });
  showSound();
  async function claim(key) {
    const storageKey = 'chromebooks:alert:' + key;
    const run = () => {
      if (memory.has(key)) return false;
      memory.add(key);
      try {
        if (localStorage.getItem(storageKey)) return false;
        localStorage.setItem(storageKey, String(Date.now()));
      } catch {
        status.textContent = 'Armazenamento bloqueado: alertas podem se repetir ao reabrir a página.';
      }
      return true;
    };
    return navigator.locks ? navigator.locks.request(storageKey, run) : run();
  }
  async function refresh() {
    if (stopped) return;
    try {
      const response = await fetch('/admin/estado', { cache: 'no-store', credentials: 'same-origin' });
      if (response.status === 401) {
        stopped = true; queuedSound = false; if (audio) audio.close(); content.replaceChildren(); alertBox.replaceChildren();
        status.textContent = 'Sessão encerrada. Entre novamente no painel.';
        const link = document.createElement('a'); link.href = '/admin/login'; link.textContent = 'Entrar';
        status.append(' ', link); return;
      }
      if (!response.ok) throw new Error('fetch');
      const data = await response.json();
      const editing = dirty || content.contains(document.activeElement);
      if (!editing) {
        const opened = [...content.querySelectorAll('details[open][id]')].map(d => d.id);
        content.innerHTML = data.html;
        window.DevicePicker?.initialize(content);
        for (const id of opened) { const detail = document.getElementById(id); if (detail) detail.open = true; }
      } // HTML escapado por Jinja, somente endpoint autenticado.
      status.textContent = editing
        ? 'Seleção preservada. Alertas atualizados; envie o formulário ou recarregue para atualizar as listas.'
        : 'Painel atualizado. Nova consulta em 15 segundos.';
      let shouldRing = false;
      const events = [
        ...(data.pending || []).map(loan => ({ key: `new:${loan.id}`, id: loan.id, phase: 'new' })),
        ...LoanAlerts.pendingAlerts(data.loans, Date.parse(data.server_time)),
      ];
      for (const event of events) {
        if (!(await claim(event.key))) continue;
        const message = document.createElement('p'); message.className = 'notice error';
        message.textContent = event.phase === 'new'
          ? `Novo pedido #${event.id}: aguardando entrega pela TI.`
          : event.phase === 'soon'
          ? `Pedido #${event.id}: devolução prevista em até 5 minutos.`
          : `Pedido #${event.id}: chegou o horário de devolução.`;
        alertBox.prepend(message);
        while (alertBox.children.length > 10) alertBox.lastElementChild.remove();
        shouldRing = true;
      }
      if (shouldRing) beep();
    } catch {
      status.textContent = 'Sem atualização: confira a conexão. Os dados exibidos podem estar desatualizados.';
    } finally {
      if (!stopped) setTimeout(refresh, 15000);
    }
  }
  refresh();
})();
