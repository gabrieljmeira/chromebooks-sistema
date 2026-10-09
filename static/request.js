// O teclado numérico não precisa oferecer dois-pontos: o campo os insere.
const returnTime = document.getElementById('expected_return');
if (returnTime) {
  returnTime.addEventListener('input', () => {
    const original = returnTime.value;
    const cursor = returnTime.selectionStart ?? original.length;
    const digitsBeforeCursor = original.slice(0, cursor).replace(/\D/g, '').length;
    const digits = original.replace(/\D/g, '').slice(0, 4);
    returnTime.value = digits.length > 2
      ? `${digits.slice(0, 2)}:${digits.slice(2)}`
      : digits;
    const position = Math.min(
      digitsBeforeCursor + (digitsBeforeCursor > 2 ? 1 : 0),
      returnTime.value.length,
    );
    returnTime.setSelectionRange(position, position);
  });
}
