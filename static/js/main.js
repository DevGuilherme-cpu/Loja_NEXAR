// Animações gerais do site
(() => {
  const anima = window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  // nível escolhido por qualidade.js: no baixo, a rolagem é a do navegador e nada entra animado ao rolar
  const leve = document.documentElement.dataset.qualidade === 'baixo';
  const temMouse = !leve && matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (!anima) return;

  // rolagem suave
  if (window.Lenis && !leve) {
    const lenis = new Lenis({ lerp: 0.12 });
    gsap.ticker.add(t => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
  }

  // quebra o título em letras; o leitor de tela lê a cópia escondida (.sr), não as letras soltas
  const dividir = el => {
    const texto = el.textContent.trim();
    el.textContent = '';
    el.setAttribute('data-split', '');
    texto.split(' ').forEach((palavra, i, todas) => {
      const p = document.createElement('span');
      p.className = 'p';
      p.setAttribute('aria-hidden', 'true');
      for (const letra of palavra) {
        const l = document.createElement('span');
        l.className = 'l';
        l.textContent = letra;
        p.append(l);
      }
      el.append(p, i < todas.length - 1 ? ' ' : '');
    });
    const sr = document.createElement('span');
    sr.className = 'sr';
    sr.textContent = texto;
    el.append(sr);
    return el.querySelectorAll('.l');
  };

  // título do hero: sobe junto com as peças caindo
  document.querySelectorAll('[data-split]').forEach(el => {
    gsap.from(dividir(el), { yPercent: 115, duration: 1, ease: 'expo.out', stagger: 0.025, delay: 0.9 });
  });

  // títulos das seções: as letras sobem quando o título aparece na tela
  const titulos = new IntersectionObserver(entradas => entradas.forEach(e => {
    if (!e.isIntersecting) return;
    titulos.unobserve(e.target);
    gsap.to(e.target.querySelectorAll('.l'), { yPercent: 0, duration: 0.8, ease: 'expo.out', stagger: 0.02 });
  }));
  document.querySelectorAll('.loja .secao-titulo, .loja .drop-titulo').forEach(el => {
    gsap.set(dividir(el), { yPercent: 115 });
    titulos.observe(el);
  });

  // cards e blocos que estão abaixo da dobra entram subindo e saindo do desfoque.
  // O que já aparece ao abrir a página fica parado (não pisca nem atrapalha a troca de página).
  if (!leve) {
    const revelar = new IntersectionObserver(entradas => {
      let fila = 0;
      entradas.forEach(e => {
        const el = e.target;
        if (!el.dataset.revela) {
          el.dataset.revela = e.isIntersecting ? 'ok' : 'espera';
          if (e.isIntersecting) revelar.unobserve(el);
          else gsap.set(el, { opacity: 0, y: 16, filter: 'blur(3px)' });  // opacidade, não visibility: o Tab continua chegando nele
          return;
        }
        if (!e.isIntersecting) return;
        revelar.unobserve(el);
        el.dataset.revela = 'ok';
        // receita "texts reveal" do transitions.dev: 500 ms, 3 px de blur, 40 ms entre um e outro
        gsap.to(el, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.5, ease: 'power4.out',
          delay: fila++ * 0.04, clearProps: 'opacity,transform,filter' });
      });
    });
    document.querySelectorAll('.loja .grid > .card, .loja .colecao, .loja .look, .loja .drop-banner, .loja .looks-texto')
      .forEach(el => revelar.observe(el));
  }

  if (!temMouse) return;

  // tilt nos cards, com um brilho que segue o mouse
  let ultimo = null;
  document.addEventListener('pointermove', e => {
    const img = e.target.closest?.('.card-img');
    if (ultimo && ultimo !== img) ['--rx', '--ry', '--gx', '--gy'].forEach(v => ultimo.style.removeProperty(v));
    ultimo = img;
    if (!img) return;
    const r = img.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    img.style.setProperty('--ry', `${x * 10}deg`);
    img.style.setProperty('--rx', `${-y * 10}deg`);
    img.style.setProperty('--gx', `${(x + 0.5) * 100}%`);
    img.style.setProperty('--gy', `${(y + 0.5) * 100}%`);
  });

  // botões neon puxados de leve pelo mouse (ímã)
  document.querySelectorAll('.btn-neon').forEach(b => {
    const irX = gsap.quickTo(b, '--mx', { duration: 0.4, ease: 'power3' });
    const irY = gsap.quickTo(b, '--my', { duration: 0.4, ease: 'power3' });
    b.addEventListener('pointermove', e => {
      const r = b.getBoundingClientRect();
      irX((e.clientX - r.left - r.width / 2) * 0.25);
      irY((e.clientY - r.top - r.height / 2) * 0.35);
    });
    b.addEventListener('pointerleave', () => {
      gsap.to(b, { '--mx': 0, '--my': 0, duration: 0.6, ease: 'elastic.out(1, 0.4)', overwrite: true });
    });
  });

  // prévia da foto nas categorias
  const lista = document.querySelector('.cats');
  if (!lista) return;
  const previa = document.createElement('img');
  previa.className = 'cats-previa';
  previa.alt = '';
  document.body.append(previa);
  const irX = gsap.quickTo(previa, 'x', { duration: 0.5, ease: 'power3' });
  const irY = gsap.quickTo(previa, 'y', { duration: 0.5, ease: 'power3' });
  lista.addEventListener('pointermove', e => { irX(e.clientX + 24); irY(e.clientY - 140); });
  lista.querySelectorAll('a[data-foto]').forEach(a => {
    a.addEventListener('pointerenter', () => {
      previa.src = a.dataset.foto;
      gsap.to(previa, { opacity: 1, scale: 1, rotate: gsap.utils.random(-6, 6), duration: 0.4, ease: 'back.out(2)' });
    });
    a.addEventListener('pointerleave', () => gsap.to(previa, { opacity: 0, scale: 0.6, duration: 0.25 }));
  });
})();
