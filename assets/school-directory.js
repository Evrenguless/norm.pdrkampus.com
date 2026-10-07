(() => {
  const input = document.getElementById('directorySearch');
  if (!input) return;
  const entries = [...document.querySelectorAll('[data-directory-entry]')];
  const output = document.getElementById('directoryCount');
  const normalize = value => value.toLocaleLowerCase('tr-TR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replaceAll('ı', 'i');
  const texts = entries.map(entry => normalize(entry.textContent));
  function filter() {
    const query = normalize(input.value.trim());
    let visible = 0;
    entries.forEach((entry, index) => { entry.hidden = !texts[index].includes(query); if (!entry.hidden) visible++; });
    output.textContent = visible ? visible.toLocaleString('tr-TR') + ' sonuç gösteriliyor' : 'Bu aramayla eşleşen kayıt bulunamadı.';
  }
  input.addEventListener('input', filter);
  filter();
})();
