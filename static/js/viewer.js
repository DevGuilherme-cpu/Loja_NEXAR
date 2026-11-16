// Visualizador da página do produto: arrastar gira, roda do mouse/pinça aproxima.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { criarRenderer, criarCena, criarModelo } from './pecas.js';

const canvas = document.getElementById('viewer-3d');
const renderer = criarRenderer(canvas);
const cena = criarCena(renderer);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
camera.position.set(0, 0.4, 6.5);

const controles = new OrbitControls(camera, canvas);
Object.assign(controles, {
  enableDamping: true, enablePan: false, minDistance: 3.5, maxDistance: 10,
  autoRotate: !matchMedia('(prefers-reduced-motion: reduce)').matches, autoRotateSpeed: 1.5,
});
controles.addEventListener('start', () => { controles.autoRotate = false; }); // parou de girar sozinho quando a pessoa mexe

new ResizeObserver(() => {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}).observe(canvas);

cena.add(await criarModelo({ ...canvas.dataset, seed: Number(canvas.dataset.id) }, 2.6));
canvas.classList.add('pronto');

renderer.setAnimationLoop(() => {
  controles.update();
  renderer.render(cena, camera);
});