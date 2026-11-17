// Hero da home: as peças em destaque caem no palco achatadas e inflam ao pousar.
// Depois flutuam, seguem o mouse e sobem/giram quando a página rola.
import * as THREE from 'three';
import { criarRenderer, criarCena, criarModelo } from './pecas.js';

const canvas = document.getElementById('hero-3d');
const anima = window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;
const renderer = criarRenderer(canvas, {}, 1.5); // tela cheia: 1.5x basta e não engasga no projetor
const cena = criarCena(renderer);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
camera.position.z = 9;

// [x, y, z, tamanho] de cada peça. As peças ficam onde o título não está:
// tela larga = metade direita; tablet = faixa de cima; celular = bloco 2x2 em cima.
const LAYOUT = {
  largo: [[0.55, 1.2, -0.6, 1.8], [2.35, 0.45, 0.4, 2.5], [3.95, 1.3, -0.4, 1.75], [1.05, -1.3, -0.9, 1.55]],
  medio: [[-2.55, 1.55, -0.5, 1.45], [-0.85, 1.7, 0.3, 1.75], [0.95, 1.5, 0, 1.6], [2.65, 1.7, -0.6, 1.45]],
  estreito: [[-0.85, 2.45, 0, 1.35], [0.9, 2.6, -0.3, 1.35], [-0.8, 0.85, 0.2, 1.35], [0.95, 1.0, -0.2, 1.35]],
};
const formato = aspecto => (aspecto > 1.55 ? 'largo' : aspecto > 0.85 ? 'medio' : 'estreito');

const grupo = new THREE.Group();
cena.add(grupo);
const dados = [...document.querySelectorAll('#hero-pecas li')].slice(0, 4).map(li => ({ ...li.dataset }));
const pecas = await Promise.all(dados.map(async (d, i) => {
  const suporte = new THREE.Group(); // o suporte anda e estica; a peça dentro fica com a escala certa
  suporte.add(await criarModelo({ ...d, seed: i }, 1));
  suporte.userData.fase = i * 1.7;
  grupo.add(suporte);
  return suporte;
}));

let atual = null;
function posicionar() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  const agora = formato(camera.aspect);
  camera.position.z = agora === 'estreito' ? 10.5 : 9;
  camera.updateProjectionMatrix();
  if (agora === atual) return;
  atual = agora;
  pecas.forEach((p, i) => {
    const [x, y, z, s] = LAYOUT[agora][i];
    p.userData.base = { x, y, z };
    p.position.set(x, y, z);
    p.children[0].scale.setScalar(s * (p.children[0].userData.escala ??= p.children[0].scale.x));
  });
}
new ResizeObserver(posicionar).observe(canvas);
posicionar();

// ---------- a queda: o único momento que acontece sozinho na página ----------
let pousou = !anima;
if (anima) {
  pecas.forEach(p => { p.position.y += 7; p.scale.set(1.15, 1, 0.04); p.rotation.set(0.6, -0.8, 0.3); });
  gsap.timeline({ delay: 0.2, onComplete: () => { pousou = true; } })
    .to(pecas.map(p => p.position), { y: i => pecas[i].userData.base.y, duration: 1.1, ease: 'bounce.out', stagger: 0.14 })
    .to(pecas.map(p => p.rotation), { x: 0, y: 0, z: 0, duration: 1.2, ease: 'power3.out', stagger: 0.14 }, 0)
    .to(pecas.map(p => p.scale), { x: 1, z: 1, duration: 1.3, ease: 'elastic.out(1, 0.45)', stagger: 0.14 }, 0.75);
}

// ---------- depois: flutua, segue o mouse e reage à rolagem ----------
const mouse = { x: 0, y: 0 };
addEventListener('pointermove', e => {
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = (e.clientY / innerHeight) * 2 - 1;
});
let visivel = true;
new IntersectionObserver(([e]) => { visivel = e.isIntersecting; }).observe(canvas);

const relogio = new THREE.Clock();
renderer.setAnimationLoop(() => {
  if (!visivel) return;
  const t = anima ? relogio.getElapsedTime() : 0;
  const rolagem = Math.min(scrollY / innerHeight, 1);
  if (pousou) {
    pecas.forEach(p => {
      const f = p.userData.fase;
      p.position.y = p.userData.base.y + Math.sin(t * 0.9 + f) * 0.08;
      p.rotation.y = Math.sin(t * 0.35 + f) * 0.35;
    });
  }
  // o "+= (alvo - atual) * 0.06" deixa o movimento macio, sem tranco
  grupo.rotation.x += (mouse.y * 0.18 + rolagem * 0.5 - grupo.rotation.x) * 0.06;
  grupo.rotation.y += (mouse.x * 0.35 - grupo.rotation.y) * 0.06;
  grupo.position.y = rolagem * 2.2;
  renderer.render(cena, camera);
});
