(() => {
  const content = document.getElementById('dashboard-content');
  const status = document.getElementById('sync-status');
  const alertBox = document.getElementById('alerts');
  const toggle = document.getElementById('sound-toggle');
  let sound = false, audio = null, dirty = false, stopped = false;
  const memory = new Set();
  content.addEventListener('change', () => { dirty = true; });
  content.addEventListener('input', () => { dirty = true; });
  toggle.addEventListener('click', async () => {
    try {
      if (!sound) {
        const Audio = window.AudioContext || window.webkitAudioContext;
        audio = audio || new Audio();
        await audio.resume();
        if (audio.state !== 'running') throw new Error('audio');
      }
      sound = !sound;
      toggle.textContent = sound ? 'Silenciar som' : 'Ativar som';
      toggle.setAttribute('aria-pressed', String(sound));
    } catch {
      sound = false;
      status.textContent = 'Som indisponível neste navegador. Os alertas visuais continuam ativos.';
    }
  });
  function beep() {
    if (!sound || !audio || audio.state !== 'running') return;
    const tone = audio.createOscillator(), gain = audio.createGain();
    tone.connect(gain); gain.connect(audio.destination);
    tone.frequency.value = 740;
    gain.gain.setValueAtTime(0.12, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.5);
    tone.start(); tone.stop(audio.currentTime + 0.5);
    tone.onended = () => { tone.disconnect(); gain.disconnect(); };
  }
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
      if (!editing) content.innerHTML = data.html; // HTML escapado por Jinja, somente endpoint autenticado.
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
