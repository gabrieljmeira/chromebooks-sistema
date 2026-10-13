(() => {
  const search = document.getElementById('history-search');
  const status = document.getElementById('history-status');
  const items = [...document.querySelectorAll('.history-item')];
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function filter() {
    const query = normalize(search.value.trim());
    let count = 0;
    for (const item of items) {
      const match = !status.value || (status.value === 'overdue' ? item.dataset.overdue === '1'
        : status.value === 'review' ? item.dataset.review === '1' : item.dataset.status === status.value);
      item.hidden = !(match && normalize(item.dataset.search).includes(query));
      if (!item.hidden) count++;
    }
    document.getElementById('history-count').textContent = `${count} pedido(s) encontrado(s) nos registros carregados.`;
  }
  search.addEventListener('input', filter);
  status.addEventListener('change', filter);
  filter();
})();
