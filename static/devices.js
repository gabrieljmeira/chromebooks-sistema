(() => {
  function update(form) {
    const boxes = [...form.querySelectorAll('input[name="devices"]')];
    const count = boxes.filter(box => box.checked && !box.matches(':disabled')).length;
    const exact = form.dataset.deviceCount !== 'any';
    const expected = Number(form.dataset.deviceCount);
    const valid = exact ? count === expected : count > 0;
    const hint = form.querySelector('.selection-count');
    if (hint) hint.textContent = exact ? `${count} de ${expected} aparelhos selecionados.` : `${count} aparelho(s) selecionado(s) para devolução.`;
    // A primeira caixa representa a validação do grupo; o servidor revalida tudo.
    const first = boxes.find(box => !box.matches(':disabled'));
    if (first) first.setCustomValidity(valid ? '' : exact
      ? `Selecione exatamente ${expected} aparelhos.` : 'Selecione pelo menos um aparelho recebido.');
    const button = form.querySelector('[data-select-available]');
    if (button && exact) {
      const available = boxes.filter(box => !box.matches(':disabled')).length;
      const blocked = button.dataset.selectionBlocked === 'true';
      button.closest('.device-shortcuts').hidden = false;
      button.disabled = blocked || available < expected;
      form.querySelector('.quick-selection-help').textContent = blocked
        ? 'Confira os códigos dos empréstimos antigos antes de selecionar.'
        : available < expected
        ? `Há ${available} ${available === 1 ? 'disponível' : 'disponíveis'}; este pedido precisa de ${expected}.`
        : 'Em ordem numérica. Substitui a seleção atual.';
    }
  }
  function initialize(root = document) {
    root.querySelectorAll('form[data-device-count]').forEach(update);
  }
  document.addEventListener('change', event => {
    const form = event.target.closest('form[data-device-count]');
    if (form) update(form);
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-select-available]');
    const form = button?.closest('form[data-device-count]');
    if (!form || button.disabled || form.dataset.deviceCount === 'any') return;
    const boxes = [...form.querySelectorAll('input[name="devices"]')];
    const expected = Number(form.dataset.deviceCount);
    const available = boxes.filter(box => !box.matches(':disabled'))
      .sort((a, b) => a.value.localeCompare(b.value, 'pt-BR', {numeric: true}));
    if (button.dataset.selectionBlocked === 'true' || available.length < expected) {
      update(form); return;
    }
    const selected = new Set(available.slice(0, expected));
    for (const box of boxes) box.checked = selected.has(box);
    // A atualização do painel preserva a seleção automática como uma edição manual.
    form.dispatchEvent(new Event('change', {bubbles: true}));
  });
  window.DevicePicker = { initialize };
  initialize();
})();
