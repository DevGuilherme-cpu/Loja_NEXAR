import * as THREE from 'three';
import { criarRenderer, criarCena, criarModelo } from './pecas.js';

const imagens = [...document.querySelectorAll('img[data-thumb]')];

if (imagens.length) {
  const canvas = document.createElement('canvas');
  const renderer = criarRenderer(canvas, { preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(640, 800, false);
  const cena = criarCena(renderer);
  const camera = new THREE.PerspectiveCamera(30, 640 / 800, 0.1, 100);
  camera.position.set(0, 0, 7);

    // Gira o modelo, desenha e devolve a imagem
    const foto = (modelo, giro) => {
      modelo.rotation.set(0.15, giro, 0);
      renderer.render(cena, camera);
      return canvas.toDataURL('image/png');
    };
  
    for (const img of imagens) {
      const modelo = await criarModelo({ ...img.dataset, seed: Number(img.dataset.id) });
      cena.add(modelo);
      img.src = foto(modelo, -0.5);                       // frente
      const verso = img.parentElement.querySelector('.card-img-2');
      if (verso) verso.src = foto(modelo, Math.PI - 0.5); // costas (aparece no hover)
      img.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 600 });
      cena.remove(modelo);
    }
}