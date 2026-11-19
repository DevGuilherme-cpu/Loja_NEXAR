// Contagem do drop da home (a data de fim vem do servidor: views.FIM_DROP)
(() => {
  const caixa = document.querySelector('.contagem');
  if (!caixa) return;
  const fim = Date.parse(caixa.dataset.fim);
  const campos = Object.fromEntries([...caixa.querySelectorAll('[data-unidade]')].map(b => [b.dataset.unidade, b]));
  const dois = n => String(n).padStart(2, '0');

  const atualizar = () => {
    const s = Math.max(0, Math.floor((fim - Date.now()) / 1000));
    campos.dias.textContent = dois(Math.floor(s / 86400));
    campos.horas.textContent = dois(Math.floor(s / 3600) % 24);
    campos.min.textContent = dois(Math.floor(s / 60) % 60);
    campos.seg.textContent = dois(s % 60);
    if (!s) { caixa.querySelector('p').textContent = 'Drop encerrado'; clearInterval(relogio); }
  };
  const relogio = setInterval(atualizar, 1000);
  atualizar();
})();
