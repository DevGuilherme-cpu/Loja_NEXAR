// "Adicionar à sacola" sem recarregar a página: o servidor responde em JSON, uma bolinha voa até a
// sacola do topo, o número pula e um aviso aparece embaixo. Sem JavaScript, o mesmo botão funciona
// com recarga (o servidor redireciona de volta ao produto com a mensagem).
(() => {
  const form = document.querySelector('.pdp-form');
  const botao = form?.querySelector('[data-sacola-adicionar]');
  const link = document.querySelector('[data-sacola]');
  if (!botao || !link) return;
  const contador = link.querySelector('[data-sacola-qtd]');
  // mesma condição do viewer.js: com animação, ele gira a peça primeiro e reenvia o formulário
  const anima = window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;

  // aviso (toast). Fica sempre no HTML e vazio: leitores de tela anunciam quando o texto muda
  const aviso = document.createElement('div');
  aviso.className = 'toast';
  aviso.setAttribute('role', 'status');
  aviso.innerHTML = '<p></p><a class="btn-sm" hidden>Ver sacola</a>';
  aviso.querySelector('a').href = link.href;
  document.body.append(aviso);
  let fecha = null;

  const avisar = (texto, ok) => {
    aviso.querySelector('p').textContent = texto;
    aviso.querySelector('a').hidden = !ok;
    aviso.classList.toggle('toast-erro', !ok);
    aviso.classList.add('aberto');
    clearTimeout(fecha);
    fecha = setTimeout(() => aviso.classList.remove('aberto'), 5000);
  };

  const contar = n => {
    contador.textContent = n;
    contador.hidden = !n;
    link.setAttribute('aria-label', `Sacola, ${n} peça${n === 1 ? '' : 's'}`);
    contador.classList.remove('pulou');
    void contador.offsetWidth;  // reinicia a animação
    contador.classList.add('pulou');
  };

  // bolinha neon do botão até a sacola, num arco (x e y com curvas diferentes)
  const voar = pronto => {
    if (!anima) return pronto();
    const de = botao.getBoundingClientRect();
    const para = link.getBoundingClientRect();
    const bola = document.createElement('span');
    bola.className = 'sacola-voo';
    document.body.append(bola);
    gsap.set(bola, { x: de.left + de.width / 2, y: de.top + de.height / 2 });
    gsap.timeline({ onComplete: () => { bola.remove(); pronto(); } })
      .to(bola, { x: para.left + para.width / 2, duration: 0.6, ease: 'power1.inOut' }, 0)
      .to(bola, { y: para.top + para.height / 2, duration: 0.6, ease: 'back.in(1.6)' }, 0)
      .to(bola, { scale: 0.45, duration: 0.6, ease: 'power2.in' }, 0);
  };

  form.addEventListener('submit', async e => {
    if (e.submitter !== botao) return;
    if (anima && !form.dataset.enviando) return;  // 1º envio: o viewer.js gira a peça e reenvia
    e.preventDefault();
    botao.disabled = true;
    try {
      const r = await fetch(botao.formAction, {
        method: 'POST', body: new FormData(form, botao), headers: { 'X-Requested-With': 'fetch' },
      });
      const dados = await r.json();
      if (dados.ok) voar(() => contar(dados.pecas));
      avisar(dados.mensagem, dados.ok);
    } catch {
      avisar('Não deu para adicionar agora. Confira a conexão e tente de novo.', false);
    } finally {
      botao.disabled = false;
      delete form.dataset.enviando;  // libera o próximo clique (e o giro do viewer.js)
    }
  });
})();
