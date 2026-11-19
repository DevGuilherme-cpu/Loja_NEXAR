// Animação do pedido confirmado: a peça entra na caixa, ganha a etiqueta, vai para o caminhão e o caminhão sai.
// Só toca logo depois da compra (a view inclui o HTML uma vez só). Não muda o status do pedido: é só a confirmação.
// Curvas e tempos seguem as receitas do transitions.dev (modal 250 ms, texto com blur de 3 px e 40 ms entre linhas).
(() => {
  const tela = document.getElementById('anim-pedido');
  if (!tela) return;
  if (!window.gsap || matchMedia('(prefers-reduced-motion: reduce)').matches) { tela.remove(); return; }

  const $ = s => tela.querySelector(s);
  const legenda = $('.anim-legenda');
  const caixa = $('.anim-caixa');
  const produto = $('.anim-produto');
  const caminhao = $('.anim-caminhao');
  const porta = $('.anim-porta');
  const rodas = tela.querySelectorAll('.anim-roda');
  const titulo = document.querySelector('.confirmado h1');
  const fora = [...document.body.children];  // o resto da página fica inerte enquanto a animação está aberta
  let tl = null;
  let fechou = false;

  const fala = texto => () => { legenda.textContent = texto; };

  const fechar = () => {
    if (fechou) return;
    fechou = true;
    tl?.kill();
    gsap.to(tela, {
      opacity: 0, scale: 0.96, duration: 0.25, ease: 'power4.out',  // receita "modal close"
      onComplete: () => {
        tela.remove();
        document.documentElement.classList.remove('anim-aberta');
        fora.forEach(el => { el.inert = false; });
        if (titulo) { titulo.tabIndex = -1; titulo.focus({ preventScroll: true }); }
        // a confirmação aparece como na receita "texts reveal": título sobe, o resto sai do desfoque
        if (titulo) gsap.fromTo(titulo.querySelectorAll('.l'), { yPercent: 115 },
          { yPercent: 0, duration: 0.8, ease: 'expo.out', stagger: 0.02 });
        gsap.from('.confirmado .drop-sub, .confirmado .confirmado-acoes, .confirmado .passos, .confirmado .resumo',
          { opacity: 0, y: 12, filter: 'blur(3px)', duration: 0.5, ease: 'power4.out', stagger: 0.04, delay: 0.1,
            clearProps: 'opacity,transform,filter' });
      },
    });
  };

  try {
    document.body.append(tela);  // sai de dentro do <main> para poder deixar o resto inerte
    fora.forEach(el => { el.inert = true; });
    document.documentElement.classList.add('anim-aberta');
    tela.hidden = false;

    const pular = $('.anim-pular');
    pular.addEventListener('click', fechar);
    tela.addEventListener('keydown', e => { if (e.key === 'Escape') fechar(); });
    pular.focus({ preventScroll: true });
    setTimeout(fechar, 10000);  // segurança: nunca prende a pessoa aqui

    const abaE = $('.anim-aba-esq');
    const abaD = $('.anim-aba-dir');
    // centro da porta do caminhão em relação ao centro da caixa (lido quando o caminhão já parou)
    const ate = eixo => () => {
      const p = porta.getBoundingClientRect();
      const c = caixa.getBoundingClientRect();
      return eixo === 'x' ? p.left + p.width / 2 - (c.left + c.width / 2) : p.top + p.height / 2 - (c.top + c.height / 2);
    };

    tl = gsap.timeline({ onComplete: fechar });
    tl
      // abre como modal
      .from(tela, { opacity: 0, duration: 0.25, ease: 'power4.out' }, 0)
      .from('.anim-palco', { scale: 0.96, duration: 0.25, ease: 'power4.out' }, 0)
      // 1. a peça e a caixa aparecem
      .from(produto, { opacity: 0, scale: 0.85, y: 12, filter: 'blur(3px)', duration: 0.6, ease: 'power4.out' }, 0.15)
      .from(caixa, { opacity: 0, y: 24, duration: 0.5, ease: 'power3.out' }, 0.35)
      // 2. abas abrem, a peça desce, abas fecham
      .add(fala('Embalando sua peça'), 1)
      .to(abaE, { rotate: -125, duration: 0.35, ease: 'back.out(1.6)' }, 1)
      .to(abaD, { rotate: 125, duration: 0.35, ease: 'back.out(1.6)' }, 1.05)
      .to(produto, { yPercent: 80, scale: 0.7, duration: 0.55, ease: 'power2.inOut' }, 1.25)
      .to(produto, { opacity: 0, duration: 0.15 }, 1.65)
      .to(abaE, { rotate: 0, duration: 0.25, ease: 'power2.in' }, 1.75)
      .to(abaD, { rotate: 0, duration: 0.25, ease: 'power2.in' }, 1.83)
      .to(caixa, { scaleY: 0.94, scaleX: 1.03, transformOrigin: '50% 100%', duration: 0.1, yoyo: true, repeat: 1 }, 2.08)
      // 3. etiqueta com o número do pedido
      .add(fala('Etiqueta de envio pronta'), 2.1)
      .fromTo('.anim-etiqueta', { opacity: 0, scale: 1.25, rotate: -8 },
        { opacity: 1, scale: 1, rotate: -3, duration: 0.4, ease: 'back.out(2)' }, 2.15)
      .to('.anim-etiqueta path', { strokeDashoffset: 0, duration: 0.3, ease: 'power2.out' }, 2.4)
      // 4. o caminhão chega pela esquerda
      .add(fala('O caminhão chegou'), 2.7)
      // entra e sai pelas bordas da tela (não do palco), em qualquer largura
      .fromTo(caminhao, { x: () => -caminhao.getBoundingClientRect().right - 20 },
        { x: 0, duration: 0.8, ease: 'power3.out' }, 2.7)
      .to(rodas, { rotation: '+=540', svgOrigin: '0 0', duration: 0.8, ease: 'power3.out' }, 2.7)
      .to('.anim-caminhao-svg', { y: -3, duration: 0.12, yoyo: true, repeat: 1 }, 3.45)
      // 5. porta abre, a caixa entra, porta fecha
      .to(porta, { scaleX: 0.06, transformOrigin: '0% 50%', duration: 0.25, ease: 'power2.inOut' }, 3.5)
      .to(caixa, { x: ate('x'), y: ate('y'), scale: 0.4, transformOrigin: '50% 50%', duration: 0.45, ease: 'power2.in' }, 3.65)
      .to(caixa, { opacity: 0, duration: 0.12 }, 3.98)
      .to(porta, { scaleX: 1, duration: 0.2, ease: 'power2.out' }, 4.1)
      // 6. o caminhão acelera para a direita
      .add(fala('Saindo para o centro de distribuição'), 4.2)
      .to(caminhao, { x: () => innerWidth - caminhao.getBoundingClientRect().left + 40, duration: 1.2, ease: 'power3.in' }, 4.25)
      .to(rodas, { rotation: '+=1440', svgOrigin: '0 0', duration: 1.2, ease: 'power3.in' }, 4.25)
      .to('.anim-caminhao-svg', { skewX: -6, duration: 0.3 }, 4.5)
      .fromTo('.anim-vento', { scaleX: 0, opacity: 0 }, { scaleX: 1, opacity: 1, duration: 0.3, stagger: 0.05 }, 4.55)
      // 7. respiro antes de mostrar a confirmação
      .add(fala('Pedido confirmado'), 5.4)
      .to({}, { duration: 0.3 });
  } catch (erro) {
    console.error(erro);
    fechar();
  }
})();
