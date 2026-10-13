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
