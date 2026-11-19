// Contagem do drop da home (a data de fim vem do servidor: views.FIM_DROP)
(() => {
  const caixa = document.querySelector('.contagem');
  if (!caixa) return;
  const fim = Date.parse(caixa.dataset.fim);
  const campos = Object.fromEntries([...caixa.querySelectorAll('[data-unidade]')].map(b => [b.dataset.unidade, b]));
  const dois = n => String(n).padStart(2, '0');
  // só o número que mudou rola (classe .rola no CSS)
  const por = (unidade, n) => {
    const b = campos[unidade];
    if (b.textContent === dois(n)) return;
    b.textContent = dois(n);
    b.classList.remove('rola');
    void b.offsetWidth;  // reinicia a animação
    b.classList.add('rola');
  };

  const atualizar = () => {
    const s = Math.max(0, Math.floor((fim - Date.now()) / 1000));
    por('dias', Math.floor(s / 86400));
    por('horas', Math.floor(s / 3600) % 24);
    por('min', Math.floor(s / 60) % 60);
    por('seg', s % 60);
    if (!s) { caixa.querySelector('p').textContent = 'Drop encerrado'; clearInterval(relogio); }
  };
  const relogio = setInterval(atualizar, 1000);
  atualizar();
})();
