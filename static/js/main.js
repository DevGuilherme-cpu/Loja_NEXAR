// Animações gerais do site
(() => {
  const anima = window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  const temMouse = matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (!anima) return;

  // rolagem suave
  if (window.Lenis) {
    const lenis = new Lenis({ lerp: 0.12 });
    gsap.ticker.add(t => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
  }

  // título do hero
  document.querySelectorAll('[data-split]').forEach(el => {
    const texto = el.textContent.trim();
    el.setAttribute('aria-label', texto);
    el.textContent = '';
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
    gsap.from(el.querySelectorAll('.l'), { yPercent: 115, duration: 1, ease: 'expo.out', stagger: 0.025, delay: 0.9 });
  });

  if (!temMouse) return;

  // tilt nos cards
  let ultimo = null;
  document.addEventListener('pointermove', e => {
    const img = e.target.closest?.('.card-img');
    if (ultimo && ultimo !== img) { ultimo.style.removeProperty('--rx'); ultimo.style.removeProperty('--ry'); }
    ultimo = img;
    if (!img) return;
    const r = img.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    img.style.setProperty('--ry', `${x * 10}deg`);
    img.style.setProperty('--rx', `${-y * 10}deg`);
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
