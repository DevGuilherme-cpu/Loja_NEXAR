// Visualizador 3D
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { criarRenderer, criarCena, criarModelo, pintar } from './pecas.js';

const canvas = document.getElementById('viewer-3d');
const palco = canvas.closest('.pdp-3d');
const anima = window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;

const renderer = criarRenderer(canvas);
const cena = criarCena(renderer);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
camera.position.set(0, 0.4, 6.5);

const controles = new OrbitControls(camera, canvas);
Object.assign(controles, {
  enableDamping: true, enablePan: false, minDistance: 3.5, maxDistance: 10,
  autoRotate: anima, autoRotateSpeed: 1.5,
});
canvas.style.touchAction = 'pan-y';
controles.addEventListener('start', () => {
  controles.autoRotate = false;
  palco.querySelector('.pdp-dica')?.remove();
});

new ResizeObserver(() => {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}).observe(canvas);

const peca = await criarModelo({ ...canvas.dataset, seed: Number(canvas.dataset.id) }, 2.6);
cena.add(peca);
canvas.classList.add('pronto');

renderer.setAnimationLoop(() => {
  controles.update();
  renderer.render(cena, camera);
});

// troca entre 3D e fotos
const botoes = [...document.querySelectorAll('.pdp-vistas button')];
let escolheu = false;
function mostrar(vista) {
  palco.dataset.vista = vista;
  botoes.forEach(b => b.setAttribute('aria-pressed', b.dataset.vista === vista));
}
botoes.forEach(b => b.addEventListener('click', () => { escolheu = true; mostrar(b.dataset.vista); }));

// entrada
function entrar() {
  mostrar('3d');
  if (anima) gsap.from(peca.rotation, { y: -Math.PI * 2, duration: 1.6, ease: 'expo.out' });
}
if (palco.dataset.vista === '3d') entrar();
else if (anima) setTimeout(() => { if (!escolheu) entrar(); }, 900);

// tamanho muda a escala
const ESCALA = { P: 0.9, M: 1, G: 1.08, GG: 1.16 };
const base = peca.scale.x;
document.querySelectorAll('input[name="tamanho"]').forEach(radio => {
  radio.addEventListener('change', () => {
    const alvo = base * (ESCALA[radio.value] || 1);
    if (anima) gsap.to(peca.scale, { x: alvo, y: alvo, z: alvo, duration: 0.7, ease: 'back.out(3)' });
    else peca.scale.setScalar(alvo);
  });
});

// animação do comprar
const form = document.querySelector('.pdp-form');
form?.addEventListener('submit', e => {
  if (!anima || form.dataset.enviando) return;
  e.preventDefault();
  form.dataset.enviando = '1';
  palco.dataset.vista = '3d';
  gsap.timeline({ onComplete: () => form.submit() })
    .to(peca.rotation, { y: `+=${Math.PI * 2}`, duration: 0.8, ease: 'power3.inOut' })
    .to(peca.position, { y: 0.35, duration: 0.4, yoyo: true, repeat: 1, ease: 'power2.out' }, 0);
});

// cor no painel
document.querySelector('input[name="cor"]')?.addEventListener('input', e => pintar(peca, e.target.value));
