(() => {
  function update(form) {
    const boxes = [...form.querySelectorAll('input[name="devices"]')];
    const count = boxes.filter(box => box.checked).length;
    const exact = form.dataset.deviceCount !== 'any';
    const expected = Number(form.dataset.deviceCount);
    const valid = exact ? count === expected : count > 0;
    const hint = form.querySelector('.selection-count');
    if (hint) hint.textContent = exact ? `${count} de ${expected} aparelhos selecionados.` : `${count} aparelho(s) selecionado(s) para devolução.`;
    // A primeira caixa representa a validação do grupo; o servidor revalida tudo.
    if (boxes[0]) boxes[0].setCustomValidity(valid ? '' : exact
      ? `Selecione exatamente ${expected} aparelhos.` : 'Selecione pelo menos um aparelho recebido.');
  }
  function initialize(root = document) {
    root.querySelectorAll('form[data-device-count]').forEach(update);
  }
  document.addEventListener('change', event => {
    const form = event.target.closest('form[data-device-count]');
    if (form) update(form);
  });
  window.DevicePicker = { initialize };
  initialize();
})();
