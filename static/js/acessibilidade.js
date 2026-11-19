// Menu de acessibilidade (topo do site) e janelas <dialog> do site.
// Carregado no <head>: as preferências salvas valem antes da página aparecer, sem "piscar".
(() => {
  const html = document.documentElement;
  const CHAVE = 'nexar-acessibilidade';
  let estado = {};
  try { estado = JSON.parse(localStorage.getItem(CHAVE)) || {}; } catch { /* navegação privada */ }

  const aplicar = () => {
    html.style.fontSize = estado.fonte ? `${100 + estado.fonte * 12.5}%` : '';
    html.classList.toggle('a11y-pb', !!estado.pb);
    html.classList.toggle('a11y-inverter', !!estado.inverter);
    html.classList.toggle('a11y-links', !!estado.links);
  };
  const salvar = () => {
    try { localStorage.setItem(CHAVE, JSON.stringify(estado)); } catch { /* sem armazenamento: vale só nesta página */ }
  };
  aplicar();

  // VLibras (governo federal) traduz o texto para Libras. Só é baixado quando a pessoa pede,
  // porque precisa de internet: sem ela, o resto do site continua funcionando.
  function libras(avisar) {
    const botao = () => document.querySelector('[vw-access-button]');
    if (window.VLibras) { botao()?.click(); return; }
    const raiz = document.createElement('div');
    raiz.setAttribute('vw', '');
    raiz.className = 'enabled';
    raiz.innerHTML = '<div vw-access-button class="active"></div>' +
      '<div vw-plugin-wrapper><div class="vw-plugin-top-wrapper"></div></div>';
    document.body.append(raiz);
    const s = document.createElement('script');
    s.src = 'https://vlibras.gov.br/app/vlibras-plugin.js';
    s.onload = () => {
      new window.VLibras.Widget('https://vlibras.gov.br/app');
      // o widget se monta no evento "load", que já passou quando a pessoa clica
      window.dispatchEvent(new Event('load'));
      avisar('Abrindo o VLibras.');
      // abre sozinho quando o botão do widget termina de montar (ele coloca uma imagem dentro)
      let tentativas = 0;
      const espera = setInterval(() => {
        if (botao()?.querySelector('img')) { clearInterval(espera); setTimeout(() => botao().click(), 300); }
        else if (++tentativas > 30) clearInterval(espera);
      }, 300);
    };
    s.onerror = () => { raiz.remove(); avisar('O VLibras precisa de internet e não carregou agora. Tente de novo mais tarde.'); };
    document.head.append(s);
  }

  document.addEventListener('DOMContentLoaded', () => {
    // janelas (guia de medidas, confirmar encerrar conta): o <dialog> já cuida de foco e da tecla Esc
    document.querySelectorAll('[data-abre]').forEach(b => b.addEventListener('click', () =>
      document.getElementById(b.dataset.abre)?.showModal()));
    document.querySelectorAll('dialog').forEach(d => {
      d.querySelectorAll('[data-fecha]').forEach(b => b.addEventListener('click', () => d.close()));
      d.addEventListener('click', e => { if (e.target === d) d.close(); });  // clique fora fecha
    });

    const botao = document.querySelector('.a11y-botao');
    if (!botao) return;
    const menu = document.getElementById(botao.getAttribute('aria-controls'));
    const aviso = document.getElementById('a11y-aviso');
    const avisar = texto => { aviso.textContent = texto; };

    const abrir = sim => {
      botao.setAttribute('aria-expanded', String(sim));
      menu.hidden = !sim;
      if (sim) menu.querySelector('button').focus();
    };
    const marcar = () => menu.querySelectorAll('[aria-pressed]').forEach(b =>
      b.setAttribute('aria-pressed', String(!!estado[b.dataset.a11y])));
    marcar();

    botao.addEventListener('click', () => abrir(menu.hidden));
    document.addEventListener('click', e => { if (!menu.hidden && !e.target.closest('.a11y')) abrir(false); });
    menu.addEventListener('keydown', e => {
      if (e.key === 'Escape') { abrir(false); botao.focus(); }
    });

    menu.addEventListener('click', e => {
      const b = e.target.closest('[data-a11y]');
      if (!b) return;
      const acao = b.dataset.a11y;
      if (acao === 'libras') { abrir(false); libras(avisar); return; }
      if (acao === 'fonte+') estado.fonte = Math.min((estado.fonte || 0) + 1, 4);
      else if (acao === 'fonte-') estado.fonte = Math.max((estado.fonte || 0) - 1, -2);
      else if (acao === 'restaurar') estado = {};
      else estado[acao] = !estado[acao];
      aplicar();
      salvar();
      marcar();
      avisar(acao.startsWith('fonte') ? `Tamanho do texto: ${100 + (estado.fonte || 0) * 12.5}%` :
        acao === 'restaurar' ? 'Recursos de acessibilidade restaurados.' : `${b.textContent.trim()}: ${estado[acao] ? 'ligado' : 'desligado'}`);
    });
  });
})();
