// 3D da home: moletom gigante no centro, peças orbitando, reage ao mouse e à rolagem.
import * as THREE from 'three';
import { criarRenderer, criarCena, criarPeca, encaixar, CORES } from './pecas.js';

const canvas = document.getElementById('hero-3d');
const renderer = criarRenderer(canvas);
const cena = criarCena(renderer);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);

const grupo = new THREE.Group();
cena.add(grupo);
const principal = encaixar(criarPeca('moletom', '#111111'), 3.4);
grupo.add(principal);
const orbitas = ['camiseta', 'bone', 'calca', 'camiseta'].map((tipo, i) => {
  const peca = encaixar(criarPeca(tipo, CORES[(i + 1) % CORES.length]), 1.1);
  peca.userData.angulo = (i / 4) * Math.PI * 2;
  grupo.add(peca);
  return peca;
});

function ajustar() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.position.z = w < 700 ? 12 : 9; // celular: câmera mais longe pra caber tudo
  camera.updateProjectionMatrix();
}
new ResizeObserver(ajustar).observe(canvas);

const mouse = { x: 0, y: 0 };
addEventListener('pointermove', e => {
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = (e.clientY / innerHeight) * 2 - 1;
});

// Para de desenhar quando o hero sai da tela (economiza bateria)
let visivel = true;
new IntersectionObserver(([e]) => { visivel = e.isIntersecting; }).observe(canvas);

const reduzir = matchMedia('(prefers-reduced-motion: reduce)').matches;
const relogio = new THREE.Clock();

renderer.setAnimationLoop(() => {
  if (!visivel) return;
  const t = reduzir ? 0 : relogio.getElapsedTime();
  const rolagem = Math.min(scrollY / innerHeight, 1);

  principal.rotation.y = t * 0.4;
  principal.position.y = 0.3 + Math.sin(t * 1.2) * 0.12;
  orbitas.forEach((peca, i) => {
    const a = peca.userData.angulo + t * 0.35;
    peca.position.set(Math.cos(a) * 3.2, Math.sin(a * 2) * 0.4 + 0.3, Math.sin(a) * 1.6);
    peca.rotation.set(t * 0.5 + i, -a, 0);
  });

  // mouse inclina o grupo; rolar a página gira e sobe tudo (o "+= (...) * 0.05" suaviza o movimento)
  grupo.rotation.x += (mouse.y * 0.25 - grupo.rotation.x) * 0.05;
  grupo.rotation.y += (mouse.x * 0.4 + rolagem * 1.5 - grupo.rotation.y) * 0.05;
  grupo.position.y = rolagem * 1.5;

  renderer.render(cena, camera);
});