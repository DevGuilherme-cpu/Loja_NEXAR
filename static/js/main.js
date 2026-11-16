// Animações globais: cortina entre páginas, rolagem suave e elementos que aparecem ao rolar.
(() => {
    const curtain = document.querySelector('.curtain');
    const reduzir = matchMedia('(prefers-reduced-motion: reduce)').matches;
  
    // Se o GSAP não carregou (sem internet) ou o usuário pediu menos movimento: tira a cortina e não anima.
    if (!window.gsap || reduzir) { curtain.remove(); return; }
    gsap.registerPlugin(ScrollTrigger);
  
    // ---------- rolagem suave ----------
    if (window.Lenis) {
      const lenis = new Lenis({ lerp: 0.1 });
      lenis.on('scroll', ScrollTrigger.update);
      gsap.ticker.add(t => lenis.raf(t * 1000));
      gsap.ticker.lagSmoothing(0);
    }
  
    // ---------- cortina sai ao abrir a página ----------
    gsap.to(curtain, { yPercent: -100, duration: 0.9, ease: 'expo.inOut', delay: 0.15 });
  
    // ---------- cortina entra antes de trocar de página ----------
    document.addEventListener('click', e => {
      const a = e.target.closest('a');
      if (!a || a.target || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin || (url.pathname === location.pathname && url.hash)) return;
      e.preventDefault();
      gsap.fromTo(curtain, { yPercent: 100 }, {
        yPercent: 0, duration: 0.6, ease: 'expo.in',
        onComplete: () => { location.href = url.href; },
      });
    });
    // Botão "voltar" do navegador reabre a página do cache: a cortina não pode ficar fechada.
    addEventListener('pageshow', e => { if (e.persisted) gsap.set(curtain, { yPercent: -100 }); });
  
    // ---------- letras do título sobem uma a uma ----------
    document.querySelectorAll('[data-split]').forEach(el => {
      const texto = el.textContent.trim();
      el.setAttribute('aria-label', texto);
      el.textContent = '';
      for (const letra of texto) {
        const s = document.createElement('span');
        s.className = 'l';
        s.setAttribute('aria-hidden', 'true');
        s.textContent = letra;
        el.append(s);
      }
      gsap.from(el.querySelectorAll('.l'), { yPercent: 110, duration: 1.2, ease: 'expo.out', stagger: 0.06, delay: 0.7 });
    });
  
    // ---------- palavras acendem conforme rola ----------
    document.querySelectorAll('[data-words]').forEach(el => {
      const palavras = el.textContent.trim().split(/\s+/);
      el.textContent = '';
      for (const p of palavras) {
        const s = document.createElement('span');
        s.className = 'w';
        s.textContent = p + ' ';
        el.append(s);
      }
      gsap.to(el.querySelectorAll('.w'), {
        opacity: 1, stagger: 0.1, ease: 'none',
        scrollTrigger: { trigger: el, start: 'top 80%', end: 'bottom 45%', scrub: true },
      });
    });
  
    // ---------- cards e categorias aparecem ao entrar na tela ----------
    gsap.set('[data-reveal]', { y: 60, opacity: 0 });
    ScrollTrigger.batch('[data-reveal]', {
      start: 'top 92%',
      once: true,
      onEnter: els => gsap.to(els, { y: 0, opacity: 1, duration: 1, ease: 'expo.out', stagger: 0.08 }),
    });
  })();