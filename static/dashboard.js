(() => {
  const content = document.getElementById('dashboard-content');
  const status = document.getElementById('sync-status');
  const alertBox = document.getElementById('alerts');
  const toggle = document.getElementById('sound-toggle');
  const soundStatus = document.getElementById('sound-status');
  let sound = false, audio = null, dirty = false, stopped = false;
  const memory = new Set();
  try { sound = localStorage.getItem('chromebooks:sound') === 'on'; } catch {}
  function showSound() {
    toggle.textContent = sound ? 'Silenciar som' : 'Ativar som';
    toggle.setAttribute('aria-pressed', String(sound));
    soundStatus.textContent = sound
      ? (audio?.state === 'running' ? 'Som ativado.' : 'Clique em Testar som para liberar o áudio nesta página.')
      : 'Som desativado.';
  }
  async function enableAudio() {
    const Audio = window.AudioContext || window.webkitAudioContext;
    audio = audio || new Audio();
    await audio.resume();
    if (audio.state !== 'running') throw new Error('audio');
  }
  function beep() {
    if (!sound || !audio || audio.state !== 'running') { showSound(); return; }
    for (let i = 0; i < 3; i++) {
      const tone = audio.createOscillator(), gain = audio.createGain();
      const begin = audio.currentTime + i * 0.3;
      tone.connect(gain); gain.connect(audio.destination);
      tone.frequency.value = 740;
      gain.gain.setValueAtTime(0.001, begin);
      gain.gain.exponentialRampToValueAtTime(0.2, begin + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, begin + 0.24);
      tone.start(begin); tone.stop(begin + 0.25);
      tone.onended = () => { tone.disconnect(); gain.disconnect(); };
    }
  }
  async function activate() {
    try {
      await enableAudio(); sound = true;
      try { localStorage.setItem('chromebooks:sound', 'on'); } catch {}
      showSound(); beep();
    } catch {
      soundStatus.textContent = 'Não foi possível liberar o áudio. Confira o volume e as permissões de som do navegador.';
    }
  }
  toggle.addEventListener('click', () => {
    if (!sound) { activate(); return; }
    sound = false;
    try { localStorage.setItem('chromebooks:sound', 'off'); } catch {}
    showSound();
  });
  document.getElementById('sound-test').addEventListener('click', activate);
  document.addEventListener('pointerdown', () => {
    if (sound && audio?.state !== 'running') enableAudio().then(showSound).catch(showSound);
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
        stopped = true; content.replaceChildren(); alertBox.replaceChildren();
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
        for (const id of opened) { const detail = document.getElementById(id); if (detail) detail.open = true; }
      } // HTML escapado por Jinja, somente endpoint autenticado.
      status.textContent = editing
        ? 'Seleção preservada. Alertas atualizados; envie o formulário ou recarregue para atualizar as listas.'
        : 'Painel atualizado. Nova consulta em 15 segundos.';
      for (const event of LoanAlerts.pendingAlerts(data.loans, Date.parse(data.server_time))) {
        if (!(await claim(event.key))) continue;
        const message = document.createElement('p'); message.className = 'notice error';
        message.textContent = event.phase === 'soon'
          ? `Pedido #${event.id}: devolução prevista em até 5 minutos.`
          : `Pedido #${event.id}: chegou o horário de devolução.`;
        alertBox.prepend(message);
        while (alertBox.children.length > 10) alertBox.lastElementChild.remove();
        beep();
      }
    } catch {
      status.textContent = 'Sem atualização: confira a conexão. Os dados exibidos podem estar desatualizados.';
    } finally {
      if (!stopped) setTimeout(refresh, 15000);
    }
  }
  refresh();
})();
