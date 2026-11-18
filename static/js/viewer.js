// Visualizador 3D
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { criarRenderer, criarCena, criarModelo, pintar, aplicarVariante } from './pecas.js';

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

let peca = await criarModelo({ ...canvas.dataset, seed: Number(canvas.dataset.id) }, 2.6);
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

// formulário do painel: a prévia acompanha o que é escolhido, antes de salvar
const formPainel = document.querySelector('.form-painel');
if (formPainel) {
  const campo = nome => formPainel.elements[nome];
  const dados = { ...canvas.dataset, seed: Number(canvas.dataset.id) };
  let arquivoGlb = null;
  let pedido = 0;

  const corEscolhida = () => (campo('cor_automatica')?.checked ? '' : campo('cor').value);

  // troca a peça do palco (categoria ou .glb novo) com um giro de entrada
  const trocar = async () => {
    const meu = ++pedido;
    const categoria = campo('categoria').selectedOptions[0];
    const nova = await criarModelo({
      ...dados,
      categoria: categoria?.value ? categoria.textContent.trim() : dados.categoria,
      modelo: arquivoGlb || dados.modelo,
      cor: corEscolhida() || dados.cor,
    }, 2.6).catch(() => null);
    if (!nova || meu !== pedido) return;  // .glb inválido ou já chegou uma escolha mais nova
    cena.remove(peca);
    peca = nova;
    cena.add(peca);
    if (anima) gsap.from(peca.rotation, { y: -Math.PI, duration: 1, ease: 'expo.out' });
  };

  campo('categoria').addEventListener('change', trocar);
  campo('modelo_3d')?.addEventListener('change', e => {
    const f = e.target.files[0];
    if (arquivoGlb) URL.revokeObjectURL(arquivoGlb);
    arquivoGlb = f ? URL.createObjectURL(f) : null;
    trocar();
  });
  campo('cor').addEventListener('input', e => {
    if (campo('cor_automatica')) campo('cor_automatica').checked = false;
    pintar(peca, e.target.value);
  });
  campo('cor_automatica')?.addEventListener('change', trocar);

  // cartão "como vai aparecer na loja"
  const cartao = document.querySelector('.previa-card');
  if (cartao) {
    const nome = cartao.querySelector('[data-previa="nome"]');
    const preco = cartao.querySelector('[data-previa="preco"]');
    const cat = cartao.querySelector('[data-previa="categoria"]');
    const fotos = [cartao.querySelector('[data-previa="foto"]'), cartao.querySelector('[data-previa="foto2"]')];
    const atualizar = () => {
      nome.textContent = campo('nome').value.trim() || 'Nome do produto';
      const v = parseFloat(campo('preco').value);
      preco.textContent = (Number.isFinite(v) ? v : 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
      const c = campo('categoria').selectedOptions[0];
      cat.textContent = c?.value ? c.textContent.trim() : 'Categoria';
    };
    ['nome', 'preco', 'categoria'].forEach(n => campo(n).addEventListener('input', atualizar));
    atualizar();
    ['imagem', 'imagem_2'].forEach((n, i) => campo(n)?.addEventListener('change', e => {
      const f = e.target.files[0];
      if (!f) return;
      fotos[i].src = URL.createObjectURL(f);
      fotos[i].hidden = false;
      cartao.classList.toggle('tem-foto', !fotos[0].hidden);
    }));
  }
}

// personalizar (camiseta e moletom por partes; tênis pelas combinações do .glb)
const caixa = document.querySelector('.personalizar');
const partes = peca.userData.partes;
const variantes = peca.userData.variantes;
if (caixa && (partes || variantes)) {
  caixa.hidden = false;
  const abrir = caixa.querySelector('.personalizar-abrir');
  const painel = caixa.querySelector('.personalizar-painel');
  const listaPartes = caixa.querySelector('.personalizar-partes');
  const listaCores = caixa.querySelector('.personalizar-cores');
  const campoEstampa = caixa.querySelector('.personalizar-estampa');
  const textoEstampa = campoEstampa.querySelector('input');
  const saida = document.querySelector('input[name="personalizacao"]');

  const AMOSTRAS = {
    Preto: '#151515', Branco: '#f2f2ef', Areia: '#d8c7a6', Oliva: '#5b6542',
    Marinho: '#22306b', Azul: '#2747d6', Vermelho: '#c8233a', Laranja: '#e8641e',
  };
  const NOMES = {
    corpo: 'Corpo', mangas: 'Mangas', gola: 'Gola', capuz: 'Capuz', bolso: 'Bolso', estampa: 'Estampa',
    cabedal: 'Cabedal', biqueira: 'Biqueira', calcanhar: 'Calcanhar', cadarco: 'Cadarço',
    entressola: 'Entressola', sola: 'Sola',
    midnight: 'Noite', beach: 'Praia', street: 'Rua',
  };
  // posição da câmera e ponto que ela olha, para cada parte
  const VISTAS = {
    geral: [[0, 0.4, 6.5], [0, 0, 0]],
    corpo: [[0, 0.1, 5], [0, -0.1, 0]],
    mangas: [[4.3, 0.7, 3.2], [0.4, 0.2, 0]],
    gola: [[0, 2.2, 3.6], [0, 0.8, 0]],
    capuz: [[0, 2.8, 3.4], [0, 0.9, 0]],
    bolso: [[0, -0.5, 3.8], [0, -0.6, 0]],
    estampa: [[0, 0.3, 3.4], [0, 0.25, 0]],
    // tênis: comprimento no eixo x, ponta para a direita
    cabedal: [[1.2, 1.2, 4.6], [0, 0.1, 0]],
    biqueira: [[4, 0.8, 2.4], [0.9, 0, 0]],
    calcanhar: [[-4, 1, 2.4], [-0.9, 0.1, 0]],
    cadarco: [[0.8, 3.6, 2.2], [0.2, 0.3, 0]],
    entressola: [[0.5, -0.2, 4.4], [0, -0.25, 0]],
    sola: [[0.5, -3.4, 3], [0, -0.4, 0]],
  };

  const original = {};
  const escolhas = {};
  if (partes) {
    for (const [nome, meshes] of Object.entries(partes)) {
      if (nome !== 'estampa') original[nome] = '#' + meshes[0].material.color.getHexString();
    }
  }
  let parteAtual = partes ? Object.keys(partes)[0] : null;
  let varianteAtual = variantes?.padrao ?? '';
  let estampaCor = partes?.corpo?.[0].material.color.getHSL({}).l > 0.5 ? '#151515' : '#f2f2ef';
  const estampaMesh = partes?.estampa?.[0];

  const opcoes = partes ? Object.keys(partes) : variantes.nomes;
  for (const valor of opcoes) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.dataset.valor = valor;
    b.textContent = NOMES[valor] ?? valor;
    b.setAttribute('aria-pressed', String(valor === (partes ? parteAtual : variantes.padrao)));
    listaPartes.append(b);
  }
  if (partes) {
    for (const [nome, hex] of Object.entries(AMOSTRAS)) {
      const b = document.createElement('button');
      b.type = 'button';
      b.dataset.cor = hex;
      b.style.setProperty('--amostra', hex);
      b.setAttribute('aria-label', nome);
      b.title = nome;
      listaCores.append(b);
    }
  } else {
    listaCores.hidden = true;
  }

  const salvar = () => {
    const texto = textoEstampa.value.trim();
    saida.value = JSON.stringify({
      ...escolhas,
      ...(texto && { estampa: texto, estampaCor }),
      ...(variantes && varianteAtual !== variantes.padrao && { variante: varianteAtual }),
    });
  };

  const marcarCor = () => {
    const atual = parteAtual === 'estampa' ? estampaCor : escolhas[parteAtual] || original[parteAtual];
    listaCores.querySelectorAll('button').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.cor === atual?.toLowerCase())));
  };

  const ir = vista => {
    const [perto, alvo] = VISTAS[vista] || VISTAS.geral;
    // tela estreita (celular): afasta a câmera para a parte caber
    const k = camera.aspect < 0.8 ? 1.6 : 1;
    const pos = perto.map((v, i) => alvo[i] + (v - alvo[i]) * k);
    controles.autoRotate = false;
    if (!anima) {
      camera.position.set(...pos);
      controles.target.set(...alvo);
      return;
    }
    gsap.to(camera.position, { x: pos[0], y: pos[1], z: pos[2], duration: 0.9, ease: 'power3.inOut' });
    gsap.to(controles.target, { x: alvo[0], y: alvo[1], z: alvo[2], duration: 0.9, ease: 'power3.inOut' });
  };

  // a parte escolhida pisca em azul
  const destacar = meshes => {
    if (!anima) return;
    meshes.forEach(m => {
      if (!m.material.emissive) return;
      m.material.emissive.set('#2747d6');
      gsap.fromTo(m.material, { emissiveIntensity: 0.9 }, { emissiveIntensity: 0, duration: 1, ease: 'power2.out' });
    });
  };

  const branco = new THREE.Color('#ffffff');
  const pintarParte = (nome, hex) => {
    const alvo = new THREE.Color(hex);
    partes[nome].forEach(m => {
      const brilho = () => m.material.sheenColor?.copy(m.material.color).lerp(branco, 0.5);
      if (!anima) { m.material.color.copy(alvo); brilho(); return; }
      gsap.to(m.material.color, { r: alvo.r, g: alvo.g, b: alvo.b, duration: 0.5, ease: 'power2.out', onUpdate: brilho });
    });
    if (anima) {
      gsap.fromTo(peca.children[0].scale, { x: 1.04, y: 1.04, z: 1.04 },
        { x: 1, y: 1, z: 1, duration: 0.7, ease: 'elastic.out(1, 0.5)' });
    }
  };

  const desenhar = () => {
    if (!estampaMesh) return;
    const apareceu = !estampaMesh.visible;
    estampaMesh.userData.desenhar(textoEstampa.value.trim(), estampaCor);
    if (anima && apareceu && estampaMesh.visible) {
      gsap.fromTo(estampaMesh.scale, { x: 0.5, y: 0.5 }, { x: 1, y: 1, duration: 0.5, ease: 'back.out(2.5)' });
    }
  };

  // tênis: gira, troca a combinação no meio da volta e termina o giro
  const trocarVariante = nome => {
    varianteAtual = nome;
    salvar();
    if (!anima) { aplicarVariante(peca, nome); return; }
    gsap.timeline()
      .to(peca.rotation, { y: '+=' + Math.PI, duration: 0.45, ease: 'power2.in', onComplete: () => aplicarVariante(peca, nome) })
      .to(peca.rotation, { y: '+=' + Math.PI, duration: 0.6, ease: 'power3.out' });
    gsap.fromTo(peca.position, { y: 0 }, { y: 0.3, duration: 0.45, yoyo: true, repeat: 1, ease: 'power2.out' });
  };

  abrir.addEventListener('click', () => {
    const aberto = abrir.getAttribute('aria-expanded') !== 'true';
    abrir.setAttribute('aria-expanded', String(aberto));
    painel.hidden = !aberto;
    escolheu = true;
    mostrar('3d');
    if (!aberto) { ir('geral'); return; }
    if (parteAtual) { ir(parteAtual); destacar(partes[parteAtual]); }
    marcarCor();
    if (anima) gsap.from(painel.children, { y: 12, opacity: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out' });
  });

  listaPartes.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    listaPartes.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    if (variantes) { trocarVariante(b.dataset.valor); return; }
    parteAtual = b.dataset.valor;
    campoEstampa.hidden = parteAtual !== 'estampa';
    marcarCor();
    ir(parteAtual);
    destacar(partes[parteAtual]);
    if (parteAtual === 'estampa') textoEstampa.focus({ preventScroll: true });
  });

  listaCores.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (parteAtual === 'estampa') {
      estampaCor = b.dataset.cor;
      desenhar();
    } else {
      escolhas[parteAtual] = b.dataset.cor;
      pintarParte(parteAtual, b.dataset.cor);
    }
    marcarCor();
    salvar();
  });

  textoEstampa.addEventListener('input', () => { desenhar(); salvar(); });

  painel.querySelector('[data-acao="ver"]').addEventListener('click', () => {
    ir('geral');
    if (anima) gsap.to(peca.rotation, { y: '+=' + Math.PI * 2, duration: 1.4, ease: 'power3.inOut', delay: 0.3 });
  });

  painel.querySelector('[data-acao="original"]').addEventListener('click', () => {
    if (partes) {
      for (const nome of Object.keys(escolhas)) { pintarParte(nome, original[nome]); delete escolhas[nome]; }
      textoEstampa.value = '';
      desenhar();
      marcarCor();
    }
    if (variantes && varianteAtual !== variantes.padrao) {
      trocarVariante(variantes.padrao);
      listaPartes.querySelectorAll('button').forEach(x =>
        x.setAttribute('aria-pressed', String(x.dataset.valor === variantes.padrao)));
    }
    salvar();
    ir('geral');
  });
}
